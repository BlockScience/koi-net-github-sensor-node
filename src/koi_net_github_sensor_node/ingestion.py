import json
import os
import threading
import time
from datetime import datetime

import structlog
from rid_lib.types import GithubRepo
from rid_lib.ext import Bundle

from .github_client import GithubClient
from .mock_loader import GithubMockLoader

log = structlog.stdlib.get_logger()

class GithubIngestionService:
    def __init__(self, config, kobj_queue):
        self.config = config
        self.kobj_queue = kobj_queue

        api_token = (config.github.api_token or "").strip()
        env_api_token = (getattr(config.env, "GITHUB_API_TOKEN", "") or "").strip()
        if not api_token:
            api_token = env_api_token

        self.client = GithubClient(api_token=api_token)

        env_repositories = self._parse_csv(getattr(config.env, "GITHUB_REPOSITORIES", ""))
        if env_repositories:
            self.repositories = env_repositories
        else:
            self.repositories = config.github.repositories

        self.poll_interval = self._resolve_int(
            env_value=getattr(config.env, "GITHUB_POLL_INTERVAL_SECONDS", ""),
            fallback=config.github.poll_interval_seconds,
            label="GITHUB_POLL_INTERVAL_SECONDS",
        )

        env_state_path = (getattr(config.env, "GITHUB_STATE_PATH", "") or "").strip()
        self.state_path = env_state_path or getattr(config.github, "state_path", "cache/github_state.json")
        self.state_lock = threading.Lock()
        self.state = self._load_state()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Mock data configuration
        self.use_mock_data = self._resolve_bool(
            env_value=getattr(config.env, "USE_MOCK_DATA", "") or "",
            fallback=getattr(config.github, "use_mock_data", False),
        )
        self.mock_data_path = self._resolve_optional_str(
            env_value=getattr(config.env, "MOCK_DATA_PATH", "") or "",
            fallback=getattr(config.github, "mock_data_path", None),
        )

        # Override poll interval for mock mode
        if self.use_mock_data:
            self.poll_interval = self._resolve_int(
                env_value=getattr(config.env, "GITHUB_POLL_INTERVAL_SECONDS", "") or "",
                fallback=getattr(config.github, "mock_poll_interval_seconds", 60),
                label="GITHUB_POLL_INTERVAL_SECONDS",
            )

        # Initialize mock loader if enabled
        self.mock_loader = None
        if self.use_mock_data and self.mock_data_path:
            self.mock_loader = GithubMockLoader(
                mock_data_path=self.mock_data_path,
                kobj_queue=self.kobj_queue,
                log=log,
            )

    @staticmethod
    def _parse_csv(raw_value: str) -> list[str]:
        raw_value = (raw_value or "").strip()
        if not raw_value:
            return []
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    @staticmethod
    def _resolve_bool(env_value: str, fallback: bool) -> bool:
        """Resolve boolean from environment variable."""
        env_value = (env_value or "").strip().lower()
        if env_value in ("true", "1", "yes"):
            return True
        if env_value in ("false", "0", "no"):
            return False
        return fallback

    @staticmethod
    def _resolve_optional_str(env_value: str, fallback: str | None) -> str | None:
        env_value = (env_value or "").strip()
        if env_value:
            return env_value
        return fallback

    @staticmethod
    def _resolve_int(env_value: str, fallback: int, label: str) -> int:
        env_value = (env_value or "").strip()
        if not env_value:
            return fallback
        try:
            return int(env_value)
        except ValueError:
            log.warning("Invalid %s=%r, using fallback=%s", label, env_value, fallback)
            return fallback

    def _load_state(self) -> dict:
        try:
            with open(self.state_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            log.warning("Failed to load state file %s: %s", self.state_path, e)
            return {}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with self.state_lock:
                with open(self.state_path, "w") as f:
                    json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            log.warning("Failed to write state file %s: %s", self.state_path, e)

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        poll_interval = self.poll_interval
        log.info("Github ingestion starting; interval=%ss", poll_interval)
        self._stop_event.clear()

        def _run():
            while not self._stop_event.is_set():
                start = time.time()
                try:
                    self.poll_once()
                except Exception as e:
                    log.error("Github ingestion poll failed: %s", e)

                elapsed = time.time() - start
                remaining = max(0.0, poll_interval - elapsed)
                if remaining:
                    self._stop_event.wait(remaining)

        self._thread = threading.Thread(target=_run, name="github-ingestion", daemon=True)
        self._thread.start()

    def stop(self):
        if not self._thread:
            return
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None

    def poll_once(self):
        # Check if mock mode is enabled
        if self.use_mock_data:
            return self._poll_mock_data()

        repositories = self.repositories
        if not repositories:
            log.debug("No repositories configured to poll.")
            return

        log.info("Polling %d GitHub repositories...", len(repositories))

        changes_detected = False

        for repo_str in repositories:
            if "/" not in repo_str:
                log.warning("Invalid repo string '%s'; must be owner/repo", repo_str)
                continue

            owner, repo = repo_str.split("/", 1)

            log.info(f"Fetching metadata for {owner}/{repo}...")
            # Fetch minimal metadata first to check updated_at (not implemented in simple client,
            # we just fetch the object. Optimization for later.)
            repo_obj = self.client.fetch_repo_object(owner, repo)
            if not repo_obj:
                log.warning(f"Failed to fetch repo object for {owner}/{repo}")
                continue

            current_updated_at = repo_obj.updated_at
            log.info(f"Current updated_at for {owner}/{repo}: {current_updated_at}")

            # Check state
            # We store the updated_at string in state
            last_known_str = self.state.get(repo_str)
            last_known = datetime.strptime(last_known_str, '%Y-%m-%d %H:%M:%S.%f') if last_known_str else None
            log.info(f"Last known updated_at for {owner}/{repo}: {last_known}")

            should_update = False
            if not last_known:
                should_update = True
            elif current_updated_at and current_updated_at > last_known:
                should_update = True

            if should_update:
                log.info("Change detected for %s", repo_str)
                rid = GithubRepo(owner, repo)
                bundle = Bundle.generate(rid=rid, contents=repo_obj.model_dump(mode="json"))

                self.kobj_queue.push(bundle=bundle)

                # Update state
                self.state[repo_str] = str(current_updated_at)
                changes_detected = True
            else:
                log.info(f"No changes detected for {owner}/{repo}")

        if changes_detected:
            self._save_state()
        else:
            log.info("No GitHub changes detected")

    def _poll_mock_data(self):
        """Poll mock data from local files instead of GitHub API."""
        if not self.mock_loader:
            log.warning("Mock mode enabled but no mock_loader configured")
            return

        log.info("Polling mock GitHub data...")
        count = self.mock_loader.load_all()

        if count:
            log.info(f"Processed {count} mock GitHub repos")
        else:
            log.info("No mock GitHub repos to process")

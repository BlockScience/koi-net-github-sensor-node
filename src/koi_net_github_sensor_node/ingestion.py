import json
import os
import threading
import time
from datetime import datetime

import structlog
from rid_lib.types import GithubRepo
from rid_lib.ext import Bundle

from .github_client import GithubClient

log = structlog.stdlib.get_logger()

class GithubIngestionService:
    def __init__(self, config, kobj_queue):
        self.config = config
        self.kobj_queue = kobj_queue

        api_token = config.github.api_token
        if not api_token:
            try:
                api_token = config.env.GITHUB_API_TOKEN
            except Exception:
                api_token = ""

        self.client = GithubClient(api_token=api_token)

        self.state_path = getattr(config.github, "state_path", "cache/github_state.json")
        self.state_lock = threading.Lock()
        self.state = self._load_state()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

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

        poll_interval = self.config.github.poll_interval_seconds
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
        repositories = self.config.github.repositories
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

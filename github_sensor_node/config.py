import json
import logging
from pathlib import Path
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict

from koi_net.protocol.node import NodeProfile, NodeType, NodeProvides
from koi_net.config import NodeConfig as KoiNetNodeConfigBase, EnvConfig, KoiNetConfig as KoiNetCoreConfig
from rid_types import GitHubEvent

GITHUB_STATE_FILE_PATH = Path(".koi/github/github_state.json")

logger = logging.getLogger(__name__)

class GitHubRepoConfig(BaseModel):
    name: str # Format "owner/repo"

class GitHubConfig(BaseModel):
    api_url: HttpUrl = Field(default_factory=lambda: HttpUrl("https://api.github.com"))
    monitored_repositories: List[GitHubRepoConfig] = Field(default_factory=list)
    backfill_max_items: int = 50
    backfill_lookback_days: int = 30 # Default for initial backfill if no state
    backfill_state_file_path: Path = GITHUB_STATE_FILE_PATH

# Define StateType for GitHub backfill state
# Stores ETags or last modified timestamps per repository for different API endpoints
# e.g., {"owner/repo": {"commits_etag": "...", "issues_last_modified_ts": "..."}}
GitHubBackfillStateType = Dict[str, Dict[str, Optional[str]]]

class GitHubEnvConfig(EnvConfig):
    github_token: str | None = "GITHUB_TOKEN"
    github_webhook_secret: str | None = "GITHUB_WEBHOOK_SECRET"

class GitHubSensorNodeConfig(KoiNetNodeConfigBase):
    koi_net: KoiNetCoreConfig = Field(default_factory=lambda: KoiNetCoreConfig(
        node_name="github-sensor",
        node_profile=NodeProfile(
            node_type=NodeType.FULL,
            provides=NodeProvides(
                event=[GitHubEvent],
                state=[GitHubEvent]
            )
        )
    ))
    env: GitHubEnvConfig = Field(default_factory=GitHubEnvConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)


# --- GitHub Backfill State Management Functions ---
def load_github_backfill_state() -> GitHubBackfillStateType:
    """Loads the GitHub backfill state (ETags/last_modified) from a JSON file."""
    try:
        GITHUB_STATE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if GITHUB_STATE_FILE_PATH.exists():
            with open(GITHUB_STATE_FILE_PATH, "r") as f:
                state_data = json.load(f)
            logger.info(f"Loaded GitHub backfill state from '{GITHUB_STATE_FILE_PATH}': {len(state_data)} repos tracked.")
            return state_data
        else:
            logger.info(f"GitHub backfill state file '{GITHUB_STATE_FILE_PATH}' not found. Starting with empty state.")
            return {}
    except Exception as e:
        logger.error(f"Error loading GitHub backfill state file '{GITHUB_STATE_FILE_PATH}': {e}", exc_info=True)
        return {}

def save_github_backfill_state(state: GitHubBackfillStateType):
    """Saves the GitHub backfill state dictionary to a JSON file."""
    try:
        GITHUB_STATE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GITHUB_STATE_FILE_PATH, "w") as f:
            json.dump(state, f, indent=4)
        logger.debug(f"Saved GitHub backfill state to '{GITHUB_STATE_FILE_PATH}'.")
    except Exception as e:
        logger.error(f"Error writing GitHub backfill state file '{GITHUB_STATE_FILE_PATH}': {e}", exc_info=True)

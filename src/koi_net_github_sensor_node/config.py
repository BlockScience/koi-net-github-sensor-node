import os

from koi_net.config import (
    EnvConfig,
    FullNodeConfig,
    FullNodeProfile,
    KoiNetConfig,
    NodeContact,
    NodeProvides,
    ServerConfig,
)
from pydantic import BaseModel, Field, model_validator
from rid_lib.types import KoiNetNode, GithubRepo


class GithubEnvConfig(EnvConfig):
    GITHUB_API_TOKEN: str = "GITHUB_API_TOKEN"
    GITHUB_REPOSITORIES: str = "GITHUB_REPOSITORIES"
    GITHUB_POLL_INTERVAL_SECONDS: str = "GITHUB_POLL_INTERVAL_SECONDS"
    GITHUB_STATE_PATH: str = "GITHUB_STATE_PATH"
    COORDINATOR_RID: str = "COORDINATOR_RID"
    COORDINATOR_URL: str = "COORDINATOR_URL"
    # Mock data configuration
    USE_MOCK_DATA: str = "USE_MOCK_DATA"
    MOCK_DATA_PATH: str = "MOCK_DATA_PATH"


class GithubConfig(BaseModel):
    api_token: str = Field(default="")
    repositories: list[str] = Field(default_factory=list)
    poll_interval_seconds: int = Field(default=600)
    state_path: str = Field(default="./state/github_state.json")
    # Mock data configuration
    use_mock_data: bool = False
    mock_data_path: str | None = None
    mock_poll_interval_seconds: int = 60


class GithubSensorConfig(FullNodeConfig):
    github: GithubConfig = Field(default_factory=GithubConfig)
    server: ServerConfig = ServerConfig(port=8082)
    koi_net: KoiNetConfig = KoiNetConfig(
        node_name="github_sensor",
        node_profile=FullNodeProfile(
            provides=NodeProvides(
                event=[GithubRepo],
                state=[GithubRepo, KoiNetNode],
            ),
        ),
        rid_types_of_interest=[KoiNetNode],
        first_contact=NodeContact(url="http://127.0.0.1:8080/koi-net"),
    )
    env: GithubEnvConfig = Field(default_factory=GithubEnvConfig)

    @model_validator(mode="after")
    def apply_coordinator_contact_from_env(self):
        """Allow first_contact overrides before config.yaml exists."""
        coordinator_rid = (os.getenv("COORDINATOR_RID") or "").strip()
        coordinator_url = (os.getenv("COORDINATOR_URL") or "").strip()

        if coordinator_rid:
            self.koi_net.first_contact.rid = KoiNetNode.from_string(coordinator_rid)
        if coordinator_url:
            self.koi_net.first_contact.url = coordinator_url

        return self

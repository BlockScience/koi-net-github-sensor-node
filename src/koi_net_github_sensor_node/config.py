from koi_net.config.full_node import (
    FullNodeConfig,
    KoiNetConfig,
    NodeProfile,
    NodeProvides,
    ServerConfig,
)
from koi_net.config.core import EnvConfig, NodeContact
from pydantic import BaseModel, Field
from rid_lib.types import KoiNetNode, GithubRepo


class GithubEnvConfig(EnvConfig):
    GITHUB_API_TOKEN: str = "GITHUB_API_TOKEN"
    GITHUB_REPOSITORIES: str = "GITHUB_REPOSITORIES"
    GITHUB_POLL_INTERVAL_SECONDS: str = "GITHUB_POLL_INTERVAL_SECONDS"
    GITHUB_STATE_PATH: str = "GITHUB_STATE_PATH"


class GithubConfig(BaseModel):
    api_token: str = Field(default="")
    repositories: list[str] = Field(default_factory=list)
    poll_interval_seconds: int = Field(default=600)
    state_path: str = Field(default="./state/github_state.json")


class GithubSensorConfig(FullNodeConfig):
    github: GithubConfig = Field(default_factory=GithubConfig)
    server: ServerConfig = ServerConfig(port=8007)
    koi_net: KoiNetConfig = KoiNetConfig(
        node_name="github_sensor",
        node_profile=NodeProfile(
            provides=NodeProvides(
                event=[GithubRepo],
                state=[GithubRepo, KoiNetNode],
            ),
        ),
        rid_types_of_interest=[KoiNetNode],
        first_contact=NodeContact(url="http://127.0.0.1:8080/koi-net"),
    )
    env: GithubEnvConfig = Field(default_factory=GithubEnvConfig)

from koi_net.config.full_node import (
    FullNodeConfig,
    KoiNetConfig,
    NodeProfile,
    NodeProvides,
    ServerConfig,
)
from koi_net.config.core import EnvConfig
from pydantic import BaseModel, Field
from rid_lib.types import KoiNetNode, GithubRepo


class GithubEnvConfig(EnvConfig):
    GITHUB_API_TOKEN: str = "GITHUB_API_TOKEN"


class GithubConfig(BaseModel):
    api_token: str = Field(default="")
    repositories: list[str] = Field(default_factory=list)
    poll_interval_seconds: int = Field(default=600)
    state_path: str = Field(default="cache/github_state.json")


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
    )
    env: GithubEnvConfig = Field(default_factory=GithubEnvConfig)

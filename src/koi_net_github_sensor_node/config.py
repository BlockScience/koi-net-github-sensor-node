from pydantic import Field, BaseModel
from koi_net.config.full_node import FullNodeConfig

class GithubConfig(BaseModel):
    api_token: str = Field(default="")
    repositories: list[str] = Field(default_factory=list)
    poll_interval_seconds: int = Field(default=600)
    state_path: str = Field(default="cache/github_state.json")

class GithubSensorConfig(FullNodeConfig):
    github: GithubConfig = Field(default_factory=GithubConfig)

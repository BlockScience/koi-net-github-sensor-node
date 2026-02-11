from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class GithubRepoObject(BaseModel):
    """Payload for a GitHub Repository event."""
    owner: str
    repo: str
    description: Optional[str] = None
    stars: int = 0
    forks: int = 0
    updated_at: Optional[datetime] = None
    readme_content: Optional[str] = None
    license: Optional[str] = None
    default_branch: str = "main"

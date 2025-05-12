from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

# Common GitHub User Model
class GitHubUser(BaseModel):
    login: str
    id: int
    node_id: str
    avatar_url: str
    html_url: str
    type: str # User or Organization

# Common GitHub Repository Model (subset)
class GitHubRepositoryInfo(BaseModel):
    id: int
    node_id: str
    name: str
    full_name: str
    private: bool
    owner: GitHubUser
    html_url: str
    description: Optional[str] = None
    fork: bool
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime
    default_branch: str

# --- Push Event Models ---
class CommitAuthor(BaseModel):
    name: str
    email: str
    username: Optional[str] = None # May not always be present

class CommitInfo(BaseModel):
    id: str # SHA
    tree_id: str
    distinct: bool
    message: str
    timestamp: datetime
    url: str
    author: CommitAuthor
    committer: CommitAuthor
    added: List[str]
    removed: List[str]
    modified: List[str]

class PushEventPayload(BaseModel):
    ref: str
    before: str # SHA
    after: str # SHA
    repository: GitHubRepositoryInfo
    pusher: CommitAuthor # Pusher might have different structure than commit author sometimes
    sender: GitHubUser # User who triggered the event
    created: bool
    deleted: bool
    forced: bool
    compare: str # URL
    commits: List[CommitInfo]
    head_commit: Optional[CommitInfo] = None

# --- Issues Event Models ---
class Label(BaseModel):
    id: int
    node_id: str
    url: str
    name: str
    color: str
    default: bool
    description: Optional[str] = None

class Issue(BaseModel):
    url: str
    repository_url: str
    labels_url: str
    comments_url: str
    events_url: str
    html_url: str
    id: int
    node_id: str
    number: int
    title: str
    user: GitHubUser
    labels: List[Label]
    state: str # e.g. "open", "closed"
    locked: bool
    assignee: Optional[GitHubUser] = None
    assignees: List[GitHubUser]
    milestone: Optional[Dict[str, Any]] = None # Can be complex, simplified here
    comments: int
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    author_association: str
    body: Optional[str] = None # Or ""

class IssuesEventPayload(BaseModel):
    action: str # e.g., opened, edited, closed, reopened, labeled, unlabeled
    issue: Issue
    repository: GitHubRepositoryInfo
    sender: GitHubUser
    assignee: Optional[GitHubUser] = None # If action involves assignee
    label: Optional[Label] = None # If action involves label

# --- Pull Request Event Models ---
class PullRequestBranchInfo(BaseModel):
    label: str
    ref: str
    sha: str
    user: GitHubUser
    repo: GitHubRepositoryInfo

class PullRequestInfo(BaseModel):
    url: str
    id: int
    node_id: str
    html_url: str
    diff_url: str
    patch_url: str
    issue_url: str
    number: int
    state: str # "open", "closed", "merged"
    locked: bool
    title: str
    user: GitHubUser
    body: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    merge_commit_sha: Optional[str] = None
    assignee: Optional[GitHubUser] = None
    assignees: List[GitHubUser]
    requested_reviewers: List[GitHubUser]
    requested_teams: List[Dict[str, Any]] # Simplified
    labels: List[Label]
    milestone: Optional[Dict[str, Any]] = None # Simplified
    draft: bool
    commits_url: str
    review_comments_url: str
    review_comment_url: str # Template
    comments_url: str
    statuses_url: str
    head: PullRequestBranchInfo
    base: PullRequestBranchInfo
    author_association: str
    merged: Optional[bool] = None
    mergeable: Optional[bool] = None # Can be None
    rebaseable: Optional[bool] = None # Can be None
    mergeable_state: str
    merged_by: Optional[GitHubUser] = None
    comments: int
    review_comments: int
    maintainer_can_modify: bool
    commits: int
    additions: int
    deletions: int
    changed_files: int

class PullRequestEventPayload(BaseModel):
    action: str # e.g., opened, closed, reopened, edited, assigned, unassigned, review_requested, review_request_removed, labeled, unlabeled, synchronized
    number: int # PR number, redundant with pull_request.number but often present
    pull_request: PullRequestInfo
    repository: GitHubRepositoryInfo
    sender: GitHubUser
    assignee: Optional[GitHubUser] = None # If relevant to action
    label: Optional[Label] = None # If relevant to action

# Generic Webhook Payload for unrecognized events or common fields
class GenericEventPayload(BaseModel):
    # Common fields, or just use Dict[str, Any] if too variable
    repository: Optional[GitHubRepositoryInfo] = None
    sender: Optional[GitHubUser] = None
    installation: Optional[Dict[str, Any]] = None # For GitHub Apps
    organization: Optional[Dict[str, Any]] = None

# Add more specific event models as needed (e.g., StarEvent, ForkEvent, ReleaseEvent)
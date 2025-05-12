from rid_lib.core import ORN

class GitHubRepo(ORN):
    namespace = "github.repo"

    def __init__(self, owner: str, repo_name: str):
        self.owner = owner
        self.repo_name = repo_name
        # Remove super() call

    @property
    def reference(self) -> str:
        return f"{self.owner}/{self.repo_name}"

    @classmethod
    def from_reference(cls, reference: str):  # Remove return type annotation
        parts = reference.split('/')
        if len(parts) == 2:
            return cls(owner=parts[0], repo_name=parts[1])
        raise ValueError(f"Invalid GitHubRepo reference format: {reference}. Expected 'owner/repo_name'.")

    def __repr__(self):
        return f"<GitHubRepo RID: {str(self)}>"


class GitHubCommit(ORN):
    namespace = "github.commit"

    def __init__(self, owner: str, repo_name: str, commit_sha: str):
        self.owner = owner
        self.repo_name = repo_name
        self.commit_sha = commit_sha
        # Remove super() call

    @property
    def reference(self) -> str:
        return f"{self.owner}/{self.repo_name}:{self.commit_sha}"

    @classmethod
    def from_reference(cls, reference: str):  # Remove return type annotation
        parts = reference.split(':')
        if len(parts) == 2:
            repo_parts = parts[0].split('/')
            if len(repo_parts) == 2:
                return cls(owner=repo_parts[0], repo_name=repo_parts[1], commit_sha=parts[1])
        raise ValueError(f"Invalid GitHubCommit reference format: {reference}. Expected 'owner/repo_name:commit_sha'.")

    def get_repo_rid(self) -> GitHubRepo:
        return GitHubRepo(owner=self.owner, repo_name=self.repo_name)

    def __repr__(self):
        return f"<GitHubCommit RID: {str(self)}>"


class GitHubIssue(ORN):
    namespace = "github.issue"

    def __init__(self, owner: str, repo_name: str, issue_number: int):
        self.owner = owner
        self.repo_name = repo_name
        self.issue_number = issue_number
        # Remove super() call

    @property
    def reference(self) -> str:
        return f"{self.owner}/{self.repo_name}:{self.issue_number}"

    @classmethod
    def from_reference(cls, reference: str):  # Remove return type annotation
        parts = reference.split(':')
        if len(parts) == 2:
            repo_parts = parts[0].split('/')
            if len(repo_parts) == 2:
                try:
                    return cls(owner=repo_parts[0], repo_name=repo_parts[1], issue_number=int(parts[1]))
                except ValueError:
                    raise ValueError(f"Invalid issue number in GitHubIssue reference: {parts[1]}")
        raise ValueError(f"Invalid GitHubIssue reference format: {reference}. Expected 'owner/repo_name:issue_number'.")

    def get_repo_rid(self) -> GitHubRepo:
        return GitHubRepo(owner=self.owner, repo_name=self.repo_name)

    def __repr__(self):
        return f"<GitHubIssue RID: {str(self)}>"


class GitHubPullRequest(ORN):
    namespace = "github.pr"

    def __init__(self, owner: str, repo_name: str, pr_number: int):
        self.owner = owner
        self.repo_name = repo_name
        self.pr_number = pr_number
        # Remove super() call

    @property
    def reference(self) -> str:
        return f"{self.owner}/{self.repo_name}:{self.pr_number}"

    @classmethod
    def from_reference(cls, reference: str):  # Remove return type annotation
        parts = reference.split(':')
        if len(parts) == 2:
            repo_parts = parts[0].split('/')
            if len(repo_parts) == 2:
                try:
                    return cls(owner=repo_parts[0], repo_name=repo_parts[1], pr_number=int(parts[1]))
                except ValueError:
                    raise ValueError(f"Invalid PR number in GitHubPullRequest reference: {parts[1]}")
        raise ValueError(f"Invalid GitHubPullRequest reference format: {reference}. Expected 'owner/repo_name:pr_number'.")

    def get_repo_rid(self) -> GitHubRepo:
        return GitHubRepo(owner=self.owner, repo_name=self.repo_name)

    def __repr__(self):
        return f"<GitHubPullRequest RID: {str(self)}>"


class GitHubEvent(ORN):
    namespace = "github.event"

    def __init__(self, repo_full_name: str, event_id: str):
        if '/' not in repo_full_name or len(repo_full_name.split('/')) != 2:
            raise ValueError(f"Invalid repo_full_name format: {repo_full_name}. Expected 'owner/repo'.")

        self.repo_full_name = repo_full_name
        self.event_id = str(event_id)

    @property
    def reference(self) -> str:
        return f"{self.repo_full_name}:{self.event_id}"

    @classmethod
    def from_reference(cls, reference: str):
        parts = reference.split(':', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHubEvent reference format: '{reference}'. Expected 'owner/repo:event_id'.")

        repo_full_name = parts[0]
        event_id = parts[1]

        if '/' not in repo_full_name or len(repo_full_name.split('/')) != 2:
             raise ValueError(f"Invalid repository part in GitHubEvent reference: '{repo_full_name}'. Expected 'owner/repo'.")
        if not event_id:
            raise ValueError(f"Event ID part cannot be empty in GitHubEvent reference: '{reference}'.")

        return cls(repo_full_name=repo_full_name, event_id=event_id)

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from rid_lib.ext import Bundle
from koi_net.protocol.event import EventType as KoiEventType

from .core import node
from .gh_api import (
    get_repo_details,
    get_repo_commits,
    get_repo_issues,
    get_repo_pull_requests
)
from rid_types import GitHubEvent # Use GitHubEvent RID
from .config import GitHubBackfillStateType, load_github_backfill_state, save_github_backfill_state

logger = logging.getLogger(__name__)

async def backfill_repository_data(owner: str, repo_name: str, repo_state: Dict[str, Optional[str]]):
    """Performs backfill for a single repository using ETag/last_modified state."""
    repo_full_name = f"{owner}/{repo_name}"
    logger.info(f"Starting backfill for repository: {repo_full_name}")

    max_items = node.config.github.backfill_max_items

    # --- 1. Repository Details ---
    repo_details_etag = repo_state.get("repo_details_etag")
    repo_data, new_repo_details_etag = await get_repo_details(owner, repo_name, etag=repo_details_etag)
    if new_repo_details_etag:
        repo_state["repo_details_etag"] = new_repo_details_etag
    if repo_data: # Not 304
        event_id_repo = f"details_{repo_data.get('node_id', repo_data.get('id', 'static'))}"
        repo_event_rid = GitHubEvent(repo_full_name=repo_full_name, event_id=event_id_repo)
        event_contents = {"event_source_type": "backfill_repo_details", "payload": repo_data}
        event_bundle = Bundle.generate(rid=repo_event_rid, contents=event_contents)
        node.processor.handle(bundle=event_bundle, event_type=KoiEventType.UPDATE) # Details are an update to the repo's state
        logger.info(f"Backfilled GitHubEvent (repo details) for {repo_event_rid}")
    elif repo_data is None and repo_details_etag and new_repo_details_etag == repo_details_etag:
        logger.info(f"Repository details for {repo_full_name} not modified (ETag match).")
    else: # Initial fetch failed
        logger.error(f"Could not fetch repository details for {repo_full_name}. Some backfill aspects might be skipped.")

    # --- 2. Commits ---
    commits_list_etag = repo_state.get("commits_list_etag")
    # 'since' could be based on last commit's date if stored, or general lookback for initial population.
    # For now, ETag on the list is the primary change detection for the list itself.
    fetched_commits_data, new_commits_list_etag = await get_repo_commits(owner, repo_name, per_page=max_items, etag=commits_list_etag)
    if new_commits_list_etag:
        repo_state["commits_list_etag"] = new_commits_list_etag
    if fetched_commits_data: # Not a 304 for the list
        for commit_item in fetched_commits_data[:max_items]:
            commit_sha = commit_item.get("sha")
            if commit_sha:
                event_id_commit = f"commit_{commit_sha}"
                commit_event_rid = GitHubEvent(repo_full_name=repo_full_name, event_id=event_id_commit)
                event_contents = {"event_source_type": "backfill_commit", "payload": commit_item}
                event_bundle = Bundle.generate(rid=commit_event_rid, contents=event_contents)
                # Backfilled commits are often NEW unless complex state is kept for each commit SHA
                node.processor.handle(bundle=event_bundle, event_type=KoiEventType.NEW)
        logger.info(f"Backfilled {len(fetched_commits_data[:max_items])} GitHubEvents (commits) for {repo_full_name}")
    elif fetched_commits_data == [] and commits_list_etag and new_commits_list_etag == commits_list_etag:
        logger.info(f"Commits list for {repo_full_name} not modified (ETag match).")

    # --- 3. Issues ---
    issues_list_etag = repo_state.get("issues_list_etag")
    # Using 'since' with last processed issue update timestamp for more targeted fetching.
    last_processed_issue_update_ts = repo_state.get("issues_last_processed_update_ts")
    if not last_processed_issue_update_ts and node.config.github.backfill_lookback_days > 0: # Initial run for this repo
        since_date = datetime.utcnow() - timedelta(days=node.config.github.backfill_lookback_days)
        last_processed_issue_update_ts = since_date.isoformat() + "Z"

    fetched_issues_data, new_issues_list_etag = await get_repo_issues(owner, repo_name, state="all", since=last_processed_issue_update_ts, per_page=max_items, etag=issues_list_etag)
    if new_issues_list_etag:
        repo_state["issues_list_etag"] = new_issues_list_etag

    new_latest_issue_ts_for_state = repo_state.get("issues_last_processed_update_ts") # Keep track of the newest one seen in this run
    if fetched_issues_data:
        for issue_item in fetched_issues_data[:max_items]:
            issue_node_id = issue_item.get("node_id") # node_id is globally unique
            issue_updated_at = issue_item.get("updated_at")
            if issue_node_id:
                event_id_issue = f"issue_{issue_node_id}"
                issue_event_rid = GitHubEvent(repo_full_name=repo_full_name, event_id=event_id_issue)
                event_contents = {"event_source_type": "backfill_issue", "payload": issue_item}
                event_bundle = Bundle.generate(rid=issue_event_rid, contents=event_contents)
                node.processor.handle(bundle=event_bundle, event_type=KoiEventType.NEW) # Or UPDATE
                if issue_updated_at and (new_latest_issue_ts_for_state is None or issue_updated_at > new_latest_issue_ts_for_state):
                    new_latest_issue_ts_for_state = issue_updated_at
        if new_latest_issue_ts_for_state: # Only update if we processed some items
             repo_state["issues_last_processed_update_ts"] = new_latest_issue_ts_for_state
        logger.info(f"Backfilled {len(fetched_issues_data[:max_items])} GitHubEvents (issues) for {repo_full_name}")
    elif fetched_issues_data == [] and issues_list_etag and new_issues_list_etag == issues_list_etag:
        logger.info(f"Issues list for {repo_full_name} not modified (ETag match).")

    # --- 4. Pull Requests ---
    prs_list_etag = repo_state.get("prs_list_etag")
    last_processed_pr_update_ts = repo_state.get("prs_last_processed_update_ts")
    if not last_processed_pr_update_ts and node.config.github.backfill_lookback_days > 0: # Initial run
        since_date = datetime.utcnow() - timedelta(days=node.config.github.backfill_lookback_days)
        last_processed_pr_update_ts = since_date.isoformat() + "Z"

    # GitHub PRs list API does not reliably support 'since'. Sort by 'updated' and filter, or rely on ETag for list changes.
    # For now, using ETag primarily for the list.
    fetched_prs_data, new_prs_list_etag = await get_repo_pull_requests(owner, repo_name, state="all", per_page=max_items, etag=prs_list_etag)
    if new_prs_list_etag:
        repo_state["prs_list_etag"] = new_prs_list_etag

    new_latest_pr_ts_for_state = repo_state.get("prs_last_processed_update_ts")
    if fetched_prs_data:
        for pr_item in fetched_prs_data[:max_items]:
            pr_node_id = pr_item.get("node_id")
            pr_updated_at = pr_item.get("updated_at")
            if pr_node_id:
                event_id_pr = f"pr_{pr_node_id}"
                pr_event_rid = GitHubEvent(repo_full_name=repo_full_name, event_id=event_id_pr)
                event_contents = {"event_source_type": "backfill_pr", "payload": pr_item}
                event_bundle = Bundle.generate(rid=pr_event_rid, contents=event_contents)
                node.processor.handle(bundle=event_bundle, event_type=KoiEventType.NEW) # Or UPDATE
                if pr_updated_at and (new_latest_pr_ts_for_state is None or pr_updated_at > new_latest_pr_ts_for_state):
                    new_latest_pr_ts_for_state = pr_updated_at
        if new_latest_pr_ts_for_state:
            repo_state["prs_last_processed_update_ts"] = new_latest_pr_ts_for_state
        logger.info(f"Backfilled {len(fetched_prs_data[:max_items])} GitHubEvents (pull requests) for {repo_full_name}")
    elif fetched_prs_data == [] and prs_list_etag and new_prs_list_etag == prs_list_etag:
        logger.info(f"Pull requests list for {repo_full_name} not modified (ETag match).")

    logger.info(f"Finished backfill pass for repository: {repo_full_name}")


async def run_initial_backfill():
    """Runs backfill for all monitored repositories specified in the config."""
    monitored_repos = node.config.github.monitored_repositories
    if not monitored_repos:
        logger.info("No repositories configured for monitoring/backfill.")
        return

    logger.info(f"Starting initial backfill for {len(monitored_repos)} monitored repositories.")

    # Load the entire state for all repos
    overall_backfill_state: GitHubBackfillStateType = load_github_backfill_state()

    for repo_full_name_config in monitored_repos:
        repo_name = repo_full_name_config.name  # Get the string name
        parts = repo_name.split('/')
        if len(parts) == 2:
            owner, repo = parts[0], parts[1]
            # Get state for the current repository, or an empty dict if not present
            repo_specific_state = overall_backfill_state.get(repo_name, {})
            try:
                await backfill_repository_data(owner, repo, repo_specific_state)
                # Update the overall state with potentially modified state for this repo
                overall_backfill_state[repo_name] = repo_specific_state
            except Exception as e:
                logger.error(f"Error during backfill for {owner}/{repo}: {e}", exc_info=True)
        else:
            logger.warning(f"Invalid repository format in config: {repo_name}. Expected 'owner/repo'.")


    save_github_backfill_state(overall_backfill_state)
    logger.info("Initial backfill process completed for all configured repositories and state saved.")

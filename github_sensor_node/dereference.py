import logging
from typing import Optional, List, Dict, Tuple, Any

from rid_lib.core import RID
from rid_lib.ext import Bundle
from koi_net.protocol.api_models import BundlesPayload # For type hinting

from .core import node # To access cache and gh_api eventually
from .gh_api import (
    get_repo_details,
    get_commit_details,
    get_issue_details,
    get_pull_request_details
)
from rid_types import GitHubRepo, GitHubCommit, GitHubIssue, GitHubPullRequest

logger = logging.getLogger(__name__)

async def dereference_github_rid(rid: RID) -> Optional[Bundle]:
    """
    Fetches the full data for a given GitHub RID from the GitHub API
    and returns it as a Bundle.
    """
    logger.info(f"Attempting to dereference GitHub RID: {rid}")
    data: Optional[dict] = None

    try:
        if isinstance(rid, GitHubRepo):
            data, _ = await get_repo_details(owner=rid.owner, repo=rid.repo_name)
        elif isinstance(rid, GitHubCommit):
            data, _ = await get_commit_details(owner=rid.owner, repo=rid.repo_name, commit_sha=rid.commit_sha)
        elif isinstance(rid, GitHubIssue):
            data, _ = await get_issue_details(owner=rid.owner, repo=rid.repo_name, issue_number=rid.issue_number)
        elif isinstance(rid, GitHubPullRequest):
            data, _ = await get_pull_request_details(owner=rid.owner, repo=rid.repo_name, pr_number=rid.pr_number)
        else:
            logger.warning(f"Dereferencing not supported for RID type: {type(rid)}")
            return None
    except Exception as e:
        logger.error(f"Error during API call for dereferencing {rid}: {e}", exc_info=True)
        return None

    if data:
        bundle = Bundle.generate(rid=rid, contents=data)
        logger.info(f"Successfully dereferenced {rid}. Content hash: {bundle.manifest.sha256_hash}")

        # Optionally, write to cache after dereferencing
        # This helps if other nodes request it again soon.
        # The KOI-net core might also handle caching of dereferenced bundles.
        try:
            node.processor.cache.write(bundle)
            logger.info(f"Wrote dereferenced bundle for {rid} to cache.")
        except Exception as e:
            logger.error(f"Failed to write dereferenced bundle for {rid} to cache: {e}", exc_info=True)

        return bundle
    else:
        logger.warning(f"No data found when dereferencing {rid}.")
        return None

async def fetch_missing_bundles_for_payload(payload: BundlesPayload) -> BundlesPayload:
    """
    Attempts to dereference RIDs listed in payload.not_found.
    Updates the payload with successfully fetched bundles.
    """
    if not payload.not_found:
        return payload

    logger.info(f"Attempting to fetch {len(payload.not_found)} missing bundles via dereferencing.")

    newly_found_bundles: List[Bundle] = []
    rids_still_not_found: List[RID] = []

    for rid_to_fetch in payload.not_found:
        bundle = await dereference_github_rid(rid_to_fetch)
        if bundle:
            newly_found_bundles.append(bundle)
        else:
            rids_still_not_found.append(rid_to_fetch)
            logger.warning(f"Could not dereference or find data for RID: {rid_to_fetch}")

    # Update the payload
    payload.bundles.extend(newly_found_bundles)
    payload.not_found = rids_still_not_found

    if newly_found_bundles:
        logger.info(f"Successfully dereferenced {len(newly_found_bundles)} bundles.")
    if rids_still_not_found:
        logger.warning(f"{len(rids_still_not_found)} RIDs remain not found after dereferencing attempt.")

    return payload
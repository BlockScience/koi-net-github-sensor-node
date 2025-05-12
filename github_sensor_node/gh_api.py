import httpx
import logging
from typing import Optional, Dict, Any, List, Tuple

from .core import node

logger =logging.getLogger(__name__)

async def _make_github_request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    etag: Optional[str] = None,
    is_graphql: bool = False # GraphQL not currently used but kept for future
) -> Tuple[Optional[httpx.Response], Optional[str]]:
    """
    Helper function to make authenticated requests to GitHub API.
    Returns a tuple: (response_object_or_None_if_304, new_etag_or_None).
    Response object is None if status is 304, otherwise it's the httpx.Response.
    The new_etag is the ETag from the response, or the original ETag if 304.
    """
    base_url = str(node.config.github.api_url)

    headers = {
        "Accept": "application/vnd.github.v3+json", # Keep it general, specific types can be per-request if needed
        "Authorization": f"Bearer {node.config.env.github_token}" if node.config.env.github_token else "",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if not node.config.env.github_token:
        logger.warning(f"Making GitHub API request to {path} without a GITHUB_TOKEN.")

    if etag:
        headers["If-None-Match"] = etag

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        try:
            logger.debug(f"GitHub API Request: {method} {client.build_request(method, path, params=params).url} Headers: {headers}")
            response = await client.request(
                method,
                path,
                params=params,
                json=json_data,
                headers=headers
            )

            current_response_etag = response.headers.get("ETag")
            logger.debug(f"GitHub API Response: {response.status_code} {response.url} ETag: {current_response_etag}")

            if response.status_code == 304: # Not Modified
                logger.info(f"GitHub API request to {path} resulted in 304 Not Modified. Original ETag: {etag}")
                return None, etag # Return None for response body, and the original etag that was sent

            response.raise_for_status() # Raises for other 4XX/5XX responses
            return response, current_response_etag # Return response and its ETag

        except httpx.HTTPStatusError as e:
            # 304 is handled above. This catches other client/server errors.
            logger.error(f"GitHub API HTTP error for {method} {e.request.url}: {e.response.status_code} - {e.response.text}")
            # Return None for both, indicating an error where no valid response or ETag was processed.
            # The specific ETag from the error response might not be useful for subsequent requests.
            return None, e.response.headers.get("ETag") # Or just None if error ETag is not useful
        except httpx.RequestError as e:
            logger.error(f"GitHub API request error for {method} {e.request.url}: {e}")
            return None, None # Network or other request error

async def get_repo_details(owner: str, repo: str, etag: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetches details for a specific repository. Returns (data, new_etag). Data is None if 304 or error."""
    path = f"/repos/{owner}/{repo}"
    try:
        response, new_etag = await _make_github_request("GET", path, etag=etag)
        if response is None: # 304 Not Modified or error where response is None
            return None, new_etag
        return response.json(), new_etag
    except Exception as e: # Catch any other unexpected error from _make_github_request if it re-raises
        logger.error(f"Unexpected error in get_repo_details for {owner}/{repo}: {e}", exc_info=True)
        return None, None


async def get_repo_list_paged(
    path: str,
    params: Dict[str, Any],
    etag: Optional[str] = None,
    max_pages: int = 10 # Safety limit for pagination
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Fetches a list of items from a paginated GitHub API endpoint.
    Returns (all_items_list, etag_from_first_page_response).
    ETag is only for the first page; if the first page is 304, list is empty.
    """
    all_items: List[Dict[str, Any]] = []
    current_page_etag = etag # Use provided ETag for the first page request
    etag_to_return = etag  # Initialize with the input etag

    for page_num in range(1, max_pages + 1):
        params["page"] = page_num

        response, new_etag_for_this_page = await _make_github_request("GET", path, params=params, etag=current_page_etag if page_num == 1 else None)

        if page_num == 1:
            # The ETag that matters for "has the list changed since last time?" is the one from the first page.
            # If the first page is 304, the overall list is considered unchanged for this ETag.
            # If it's 200, this new_etag_for_this_page is the new ETag for the list's current state.
            etag_to_return = new_etag_for_this_page if new_etag_for_this_page else current_page_etag

        if response is None: # 304 Not Modified (should only happen on first page if ETag was provided and matched) or error
            if page_num == 1 and current_page_etag: # Explicit 304 on first page with ETag
                 logger.info(f"Paginated list for {path} (page 1) not modified (304). ETag: {current_page_etag}")
            # If it's an error, _make_github_request logs it. We stop pagination.
            break

        page_data = response.json()
        if not page_data: # Empty page, end of results
            break

        all_items.extend(page_data)

        if len(page_data) < params.get("per_page", 30): # Fewer items than requested, so it's the last page
            break

        # For subsequent pages, we don't use ETags as they are per-resource (URL).
        # The ETag for a paginated list usually refers to the first page's representation.
        current_page_etag = None

    return all_items, etag_to_return if 'etag_to_return' in locals() else etag


async def get_repo_commits(owner: str, repo: str, since: Optional[str] = None, per_page: int = 30, etag: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    path = f"/repos/{owner}/{repo}/commits"
    params: Dict[str, Any] = {"per_page": per_page}
    if since:
        params["since"] = since
    return await get_repo_list_paged(path, params, etag)

async def get_repo_issues(owner: str, repo: str, state: str = "open", since: Optional[str] = None, per_page: int = 30, etag: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    path = f"/repos/{owner}/{repo}/issues"
    params: Dict[str, Any] = {"state": state, "per_page": per_page}
    if since: # GitHub uses 'since' for issues to get items updated at or after this time.
        params["since"] = since
    return await get_repo_list_paged(path, params, etag)

async def get_repo_pull_requests(owner: str, repo: str, state: str = "open", per_page: int = 30, etag: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    path = f"/repos/{owner}/{repo}/pulls"
    params: Dict[str, Any] = {"state": state, "per_page": per_page}
    # GitHub PR list doesn't reliably use 'since'. ETag on first page or client-side filtering on 'updated_at' is more common.
    return await get_repo_list_paged(path, params, etag)

# Detail fetchers (usually for dereferencing or getting specifics not in list views)
# These can also use ETags if we cache individual items with their ETags.

async def get_commit_details(owner: str, repo: str, commit_sha: str, etag: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    path = f"/repos/{owner}/{repo}/commits/{commit_sha}"
    try:
        response, new_etag = await _make_github_request("GET", path, etag=etag)
        if response is None: return None, new_etag
        return response.json(), new_etag
    except Exception as e:
        logger.error(f"Failed to get commit details for {owner}/{repo} SHA {commit_sha}: {e}", exc_info=True)
        return None, None

async def get_issue_details(owner: str, repo: str, issue_number: int, etag: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    path = f"/repos/{owner}/{repo}/issues/{issue_number}"
    try:
        response, new_etag = await _make_github_request("GET", path, etag=etag)
        if response is None: return None, new_etag
        return response.json(), new_etag
    except Exception as e:
        logger.error(f"Failed to get issue details for {owner}/{repo} #{issue_number}: {e}", exc_info=True)
        return None, None

async def get_pull_request_details(owner: str, repo: str, pr_number: int, etag: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    path = f"/repos/{owner}/{repo}/pulls/{pr_number}"
    try:
        response, new_etag = await _make_github_request("GET", path, etag=etag)
        if response is None: return None, new_etag
        return response.json(), new_etag
    except Exception as e:
        logger.error(f"Failed to get PR details for {owner}/{repo} #{pr_number}: {e}", exc_info=True)
        return None, None

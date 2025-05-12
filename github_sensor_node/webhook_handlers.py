import logging
from typing import Dict, Any, Callable, Awaitable, Optional
import hashlib

from pydantic import ValidationError

from rid_lib.ext import Bundle
from koi_net.protocol.event import EventType as KoiEventType

from .core import node
from rid_types import GitHubEvent
from .event_models import (
    PushEventPayload,
    IssuesEventPayload,
    PullRequestEventPayload,
    GenericEventPayload,
    GitHubRepositoryInfo
)

logger = logging.getLogger(__name__)

WebhookHandlerFunc = Callable[[Dict[str, Any]], Awaitable[None]]
EVENT_HANDLERS: Dict[str, WebhookHandlerFunc] = {}

def register_gh_event_handler(event_name: str):
    def decorator(func: WebhookHandlerFunc):
        EVENT_HANDLERS[event_name] = func
        logger.info(f"Registered GitHub event handler for '{event_name}'")
        return func
    return decorator

async def process_webhook_event(
    event_type: str,
    payload_dict: Dict[str, Any],
    delivery_id: Optional[str] = None
):
    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        logger.info(
            f"Processing GitHub event '{event_type}' "
            f"with registered handler. Delivery ID: {delivery_id}"
        )
        try:
            await handler(payload_dict)
        except Exception as e:
            logger.error(
                f"Error processing GitHub event '{event_type}' "
                f"(Delivery ID: {delivery_id}): {e}",
                exc_info=True
            )
    else:
        logger.warning(
            f"No specific handler for GitHub event '{event_type}'. "
            f"Storing as generic GitHubEvent. Delivery ID: {delivery_id}"
        )
        await handle_generic_event(event_type, payload_dict, delivery_id=delivery_id)


@register_gh_event_handler("push")
async def handle_push_event(payload_dict: Dict[str, Any]):
    delivery_id = payload_dict.get("delivery_id")
    try:
        payload = PushEventPayload(**payload_dict)
    except ValidationError as e:
        logger.error(
            f"Validation error for push event payload "
            f"(Delivery ID: {delivery_id}): {e}"
        )
        return

    repo_info = payload.repository

    event_id = delivery_id or payload.after
    if not event_id or event_id == "0000000000000000000000000000000000000000":
        if payload.deleted and not payload.forced:
            event_id = f"delete_ref_{payload.ref.replace('/', '_')}_{payload.before}"
            logger.info(
                f"Branch deletion push event for ref {payload.ref}. "
                f"Event ID: {event_id}"
            )
        else:
            fallback = f"{repo_info.full_name}_push_{payload.ref}_{payload.before}_{payload.after}"
            event_id = hashlib.sha256(fallback.encode()).hexdigest()[:16]
            logger.warning(
                f"Unusual SHAs for push {repo_info.full_name}. "
                f"Generated fallback Event ID: {event_id}"
            )

    github_event_rid = GitHubEvent(
        repo_full_name=repo_info.full_name,
        event_id=str(event_id)
    )

    event_bundle_contents = {
        "webhook_event_type": "push",
        "repository": repo_info.model_dump(mode="json"),
        "payload": payload.model_dump(mode="json")
    }
    event_bundle = Bundle.generate(rid=github_event_rid, contents=event_bundle_contents)

    node.processor.handle(bundle=event_bundle, event_type=KoiEventType.NEW)
    logger.info(
        f"Processed GitHubEvent for push: {github_event_rid} "
        f"(Delivery ID: {delivery_id})"
    )


@register_gh_event_handler("issues")
async def handle_issues_event(payload_dict: Dict[str, Any]):
    delivery_id = payload_dict.get("delivery_id")
    try:
        payload = IssuesEventPayload(**payload_dict)
    except ValidationError as e:
        logger.error(
            f"Validation error for issues event payload "
            f"(Delivery ID: {delivery_id}): {e}"
        )
        return

    repo_info = payload.repository
    issue = payload.issue

    event_id = delivery_id or issue.node_id
    github_event_rid = GitHubEvent(
        repo_full_name=repo_info.full_name,
        event_id=str(event_id)
    )

    koi_event_type = (
        KoiEventType.NEW if payload.action == "opened"
        else KoiEventType.UPDATE
    )

    event_bundle_contents = {
        "webhook_event_type": "issues",
        "action": payload.action,
        "repository": repo_info.model_dump(mode="json"),
        "payload": payload.model_dump(mode="json")
    }
    event_bundle = Bundle.generate(rid=github_event_rid, contents=event_bundle_contents)

    node.processor.handle(bundle=event_bundle, event_type=koi_event_type)
    logger.info(
        f"Processed GitHubEvent for issue action '{payload.action}': "
        f"{github_event_rid} (Issue #{issue.number}, Delivery ID: {delivery_id})"
    )


@register_gh_event_handler("pull_request")
async def handle_pull_request_event(payload_dict: Dict[str, Any]):
    delivery_id = payload_dict.get("delivery_id")
    try:
        payload = PullRequestEventPayload(**payload_dict)
    except ValidationError as e:
        logger.error(
            f"Validation error for pull_request event payload "
            f"(Delivery ID: {delivery_id}): {e}"
        )
        return

    repo_info = payload.repository
    pr = payload.pull_request

    event_id = delivery_id or pr.node_id
    github_event_rid = GitHubEvent(
        repo_full_name=repo_info.full_name,
        event_id=str(event_id)
    )

    koi_event_type = (
        KoiEventType.NEW if payload.action == "opened"
        else KoiEventType.UPDATE
    )

    logger.info(
        f"Pull request {github_event_rid} (PR #{pr.number}) "
        f"action '{payload.action}' mapped to "
        f"KoiEventType.{koi_event_type.name}."
    )

    event_bundle_contents = {
        "webhook_event_type": "pull_request",
        "action": payload.action,
        "repository": repo_info.model_dump(mode="json"),
        "payload": payload.model_dump(mode="json")
    }
    event_bundle = Bundle.generate(rid=github_event_rid, contents=event_bundle_contents)

    node.processor.handle(bundle=event_bundle, event_type=koi_event_type)
    logger.info(
        f"Processed GitHubEvent for pull_request action "
        f"'{payload.action}': {github_event_rid} "
        f"(PR #{pr.number}, Delivery ID: {delivery_id})"
    )


async def handle_generic_event(
    event_type: str,
    payload_dict: Dict[str, Any],
    delivery_id: Optional[str] = None
):
    logger.info(
        f"Handling generic GitHub event '{event_type}'. "
        f"Delivery ID: {delivery_id}"
    )

    repo_info = payload_dict.get("repository")
    repo_full_name = None
    if isinstance(repo_info, dict):
        repo_full_name = repo_info.get("full_name")

    if not repo_full_name:
        logger.warning(
            f"Cannot determine repository for generic event "
            f"'{event_type}' (Delivery ID: {delivery_id})."
        )
        return

    event_id = delivery_id
    if not event_id:
        parts = {
            "event_type": event_type,
            "repo_id": repo_info.get("id", "unknown") if repo_info else "unknown",
            "sender_id": (payload_dict.get("sender", {}) or {}).get("id", "unknown"),
            "timestamp": payload_dict.get("timestamp", (repo_info or {}).get("pushed_at", ""))
        }
        try:
            raw = f"{parts['event_type']}_{parts['repo_id']}_{parts['sender_id']}_{parts['timestamp']}"
            event_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
            logger.info(
                f"Generated fallback event_id for generic event "
                f"'{event_type}': {event_id}"
            )
        except Exception as e:
            logger.error(
                f"Error generating fallback event_id for generic event "
                f"'{event_type}': {e}. Skipping."
            )
            return

    github_event_rid = GitHubEvent(
        repo_full_name=repo_full_name,
        event_id=str(event_id)
    )

    event_bundle_contents = {
        "webhook_event_type": event_type,
        "repository": repo_info,
        "payload": payload_dict
    }
    event_bundle = Bundle.generate(rid=github_event_rid, contents=event_bundle_contents)

    node.processor.handle(bundle=event_bundle, event_type=KoiEventType.NEW)
    logger.info(
        f"Stored generic GitHubEvent for '{event_type}': "
        f"{github_event_rid} (Delivery ID: {delivery_id})"
    )

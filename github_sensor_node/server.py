import logging
import asyncio
import hashlib
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Request, HTTPException, Header
from fastapi.responses import PlainTextResponse

from koi_net.protocol.api_models import (
    PollEvents, FetchRids, FetchManifests, FetchBundles,
    EventsPayload, RidsPayload, ManifestsPayload, BundlesPayload
)
from koi_net.protocol.consts import (
    BROADCAST_EVENTS_PATH, POLL_EVENTS_PATH, FETCH_RIDS_PATH,
    FETCH_MANIFESTS_PATH, FETCH_BUNDLES_PATH
)
from koi_net.processor.knowledge_object import KnowledgeSource

from .core import node
from .backfill import run_initial_backfill
from .webhook_handlers import process_webhook_event
from .dereference import fetch_missing_bundles_for_payload # For KOI-net fetch_bundles

logger = logging.getLogger(__name__)

# --- Webhook Signature Verification ---
def verify_signature(payload_body: bytes, secret_token: str, signature_header: str) -> bool:
    """Verify that the payload was sent from GitHub by validating SHA256 signature."""
    if not signature_header:
        logger.warning("X-Hub-Signature-256 header is missing!")
        return False # Or True if secret is not configured, but less secure
    if not secret_token:
        logger.warning("GITHUB_WEBHOOK_SECRET is not configured. Cannot verify signature.")
        return True # Or False to enforce having a secret

    hash_object = hmac.new(secret_token.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        logger.warning("Request signature mismatch. Expected: %s, Got: %s", expected_signature, signature_header)
        return False
    logger.info("Request signature verified.")
    return True

# --- FastAPI Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("GitHub Sensor Node FastAPI application starting...")
    node.start() # Start the KOI-net node interface

    # Run initial backfill for monitored repositories
    # This should ideally be non-blocking or run as a background task
    # if it's very long-running and server startup needs to be quick.
    logger.info("Starting initial backfill process...")
    asyncio.create_task(run_initial_backfill())

    yield # Application is running

    logger.info("GitHub Sensor Node FastAPI application shutting down...")
    node.stop() # Stop the KOI-net node interface
    logger.info("KOI-net node stopped.")


app = FastAPI(
    lifespan=lifespan,
    title="GitHub Sensor Node API",
    version="1.0.0",
    description="Handles GitHub webhooks and KOI-net protocol interactions."
)

# --- GitHub Webhook Endpoint ---
@app.post("/github/webhook", status_code=202) # GitHub expects 2xx for successful delivery
async def github_webhook_listener(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
    x_github_delivery: str = Header(None) # Delivery GUID
):
    logger.info(f"Received GitHub webhook. Event: '{x_github_event}', Delivery ID: '{x_github_delivery}'")

    if not x_github_event:
        logger.error("Missing X-GitHub-Event header.")
        raise HTTPException(status_code=400, detail="X-GitHub-Event header is required.")

    payload_body = await request.body()

    # Verify signature
    webhook_secret = node.config.env.github_webhook_secret
    if webhook_secret: # Only verify if secret is configured
        if not verify_signature(payload_body, webhook_secret, x_hub_signature_256):
            logger.error("Invalid webhook signature.")
            raise HTTPException(status_code=403, detail="Invalid signature.")
        logger.info("Webhook signature verified successfully.")
    else:
        logger.warning("No GITHUB_WEBHOOK_SECRET configured. Skipping signature verification (INSECURE).")

    try:
        payload_json = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON payload: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    # Asynchronously process the event to avoid blocking GitHub
    # Note: If processing is very long, consider a proper background task queue (e.g., Celery, ARQ)
    asyncio.create_task(process_webhook_event(x_github_event, payload_json))

    return PlainTextResponse("Webhook received.", status_code=202)


# --- KOI-net Protocol Router ---
koi_net_router = APIRouter(
    prefix="/koi-net",
    tags=["KOI-net Protocol"]
)

@koi_net_router.post(BROADCAST_EVENTS_PATH)
def broadcast_events(req: EventsPayload):
    logger.info(f"Request to {BROADCAST_EVENTS_PATH}, received {len(req.events)} event(s)")
    for event in req.events:
        logger.info(f"{event!r}")
        node.processor.handle(event=event, source=KnowledgeSource.External)


@koi_net_router.post(POLL_EVENTS_PATH)
def poll_events(req: PollEvents) -> EventsPayload:
    logger.info(f"Request to {POLL_EVENTS_PATH}")
    events = node.network.flush_poll_queue(req.rid)
    return EventsPayload(events=events)

@koi_net_router.post(FETCH_RIDS_PATH)
def fetch_rids(req: FetchRids) -> RidsPayload:
    return node.network.response_handler.fetch_rids(req)

@koi_net_router.post(FETCH_MANIFESTS_PATH)
def fetch_manifests(req: FetchManifests) -> ManifestsPayload:
    return node.network.response_handler.fetch_manifests(req)

@koi_net_router.post(FETCH_BUNDLES_PATH)
def fetch_bundles(req: FetchBundles) -> BundlesPayload:
    return node.network.response_handler.fetch_bundles(req)

app.include_router(koi_net_router)

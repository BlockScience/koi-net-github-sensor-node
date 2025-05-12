import logging

from koi_net.processor.handler import HandlerType, STOP_CHAIN
from koi_net.processor.knowledge_object import KnowledgeObject, KnowledgeSource
from koi_net.processor.interface import ProcessorInterface
from koi_net.protocol.event import EventType as KoiEventType

from rid_lib.types import KoiNetNode, KoiNetEdge

from rid_types import GitHubEvent # Aligned with SYSTEMSPEC and Phase 2 changes

from koi_net.protocol.node import NodeProfile
from koi_net.protocol.edge import EdgeType
from koi_net.protocol.helpers import generate_edge_bundle

from .core import node

logger = logging.getLogger(__name__)


@node.processor.register_handler(HandlerType.Network, rid_types=[KoiNetNode])
def coordinator_contact_handler(processor: ProcessorInterface, kobj: KnowledgeObject) -> None:
    """
    Handles discovery of new KoiNetNode objects, specifically looking for coordinators
    to establish necessary edges for network participation, discovery, and to announce
    the GitHubEvent RIDs this sensor provides.
    """
    if kobj.normalized_event_type != KoiEventType.NEW:
        logger.debug(f"Coordinator contact: Ignoring non-NEW event for KoiNetNode {kobj.rid}")
        return

    if not kobj.bundle or not kobj.bundle.contents:
        logger.warning(f"Coordinator contact: KoiNetNode {kobj.rid} KObj has no bundle/contents. Cannot process.")
        return

    try:
        discovered_node_profile = kobj.bundle.validate_contents(NodeProfile)
    except Exception as e:
        logger.error(f"Coordinator contact: Error validating NodeProfile for {kobj.rid}: {e}", exc_info=True)
        return

    is_coordinator = (
        KoiNetNode in discovered_node_profile.provides.event and
        KoiNetEdge in discovered_node_profile.provides.event
    )

    if not is_coordinator:
        logger.debug(f"Coordinator contact: Discovered node {kobj.rid} is not a coordinator.")
        return

    coordinator_rid = kobj.rid
    logger.info(f"Coordinator contact: Identified a coordinator node: {coordinator_rid}")

    # --- Edge 1: Sensor subscribes to Coordinator for network events (KoiNetNode, KoiNetEdge) ---
    sensor_subscribes_to_types = [KoiNetNode, KoiNetEdge]
    existing_edge_sensor_to_coord = processor.network.graph.get_edge_profile(
        source=processor.identity.rid, target=KoiNetNode(coordinator_rid)
    )

    propose_sensor_to_coord_edge = True
    if existing_edge_sensor_to_coord:
        if all(rid_type in existing_edge_sensor_to_coord.rid_types for rid_type in sensor_subscribes_to_types) and \
           existing_edge_sensor_to_coord.status == 'APPROVED': # Ensure it's also approved
            logger.info(f"Coordinator contact: Sensor already has an approved/suitable edge to coordinator {coordinator_rid} for network events.")
            propose_sensor_to_coord_edge = False
        else:
            logger.info(f"Coordinator contact: Edge Sensor->Coordinator {coordinator_rid} exists but needs update (types/status). Will re-propose.")

    if propose_sensor_to_coord_edge:
        logger.info(f"Coordinator contact: Proposing edge Sensor -> Coordinator {coordinator_rid} for network events.")
        edge_bundle_sensor_to_coord = generate_edge_bundle(
            source=processor.identity.rid, target=KoiNetNode(coordinator_rid),
            edge_type=EdgeType.WEBHOOK, rid_types=sensor_subscribes_to_types
        )
        processor.handle(bundle=edge_bundle_sensor_to_coord, source=KnowledgeSource.Internal)

    # --- Edge 2: Sensor announces its GitHubEvent capability to Coordinator (Coordinator proposes to subscribe) ---
    # The SYSTEMSPEC implies the Processor (or Coordinator acting on its behalf) initiates the subscription TO the Sensor.
    # The Sensor's role here is to ensure it's discoverable and its NodeProfile correctly lists GitHubEvent.
    # The `edge_negotiation_handler` (default KOI-net handler) on the Sensor side will handle APPROVING such proposals.
    # What this handler *can* do is ensure its own node information is up-to-date and sent to the coordinator.
    # This is typically done when the node starts via `node.start()` broadcasting its own node bundle.
    # This handler reacting to a *discovered* coordinator ensures this info is re-iterated if needed.

    logger.info(f"Coordinator contact: Broadcasting self-node bundle to newly discovered coordinator {coordinator_rid} to ensure it knows about me.")
    processor.network.push_event_to(
        event=KoiEventType.NEW.with_bundle(processor.identity.bundle),
        node=KoiNetNode(coordinator_rid),
        flush=True # Attempt to send immediately
    )

    # --- Fetch initial network state from Coordinator ---
    try:
        logger.info(f"Coordinator contact: Fetching current network RIDs from coordinator {coordinator_rid}")
        rid_payload = processor.network.request_handler.fetch_rids(node=KoiNetNode(coordinator_rid), rid_types=[KoiNetNode, KoiNetEdge])

        newly_discovered_rids = [
            rid for rid in rid_payload.rids
            if rid != processor.identity.rid and not processor.cache.exists(rid)
        ]

        if newly_discovered_rids:
            logger.info(f"Coordinator contact: Found {len(newly_discovered_rids)} new RIDs from coordinator. Fetching bundles.")
            bundle_payload = processor.network.request_handler.fetch_bundles(node=coordinator_rid, rids=newly_discovered_rids)
            for bundle_from_coord in bundle_payload.bundles:
                logger.info(f"Coordinator contact: Processing network bundle for {bundle_from_coord.rid} from coordinator.")
                processor.handle(bundle=bundle_from_coord, source=KnowledgeSource.External)
        else:
            logger.info("Coordinator contact: No new RIDs to fetch from coordinator at this time.")

    except Exception as e:
        logger.error(f"Coordinator contact: Error fetching network state from coordinator {coordinator_rid}: {e}", exc_info=True)

    logger.info(f"Coordinator contact: Finished processing for coordinator {coordinator_rid}.")


@node.processor.register_handler(HandlerType.Manifest, rid_types=[GitHubEvent])
def github_event_manifest_handler(processor: ProcessorInterface, kobj: KnowledgeObject) -> KnowledgeObject | None | type(STOP_CHAIN):
    """
    Custom manifest handler for incoming GitHubEvent RIDs.
    Determines if the manifest represents NEW or UPDATE knowledge based on cache.
    Prioritizes hash for change detection.
    """
    if not isinstance(kobj.rid, GitHubEvent):
        # This check is redundant if rid_types=[GitHubEvent] in decorator is effective,
        # but good for safety if other RIDs somehow reach here.
        logger.warning(f"GitHub Event Manifest Handler received non-GitHubEvent RID: {kobj.rid}. Passing through.")
        return kobj

    logger.debug(f"GitHubEvent Manifest Handler processing manifest for RID: {kobj.rid} (Event Type from KObj: {kobj.event_type})")

    prev_bundle = None
    try:
        prev_bundle = processor.cache.read(kobj.rid)
    except Exception as e:
        logger.error(f"Error reading from cache for GitHubEvent RID {kobj.rid}: {e}", exc_info=True)
        # Treat as not found if cache read fails, allows processing as NEW if appropriate.

    if prev_bundle:
        if kobj.manifest and prev_bundle.manifest and kobj.manifest.sha256_hash == prev_bundle.manifest.sha256_hash:
            logger.info(f"Incoming GitHubEvent manifest for {kobj.rid} has same hash as cached. Content unchanged. Stopping chain.")
            return STOP_CHAIN  # Special sentinel value to stop processing chain
        else:
            # Hashes are different, this is an update.
            logger.info(f"GitHubEvent RID {kobj.rid} known, content hash differs. Labeling manifest as UPDATE.")
            kobj.normalized_event_type = KoiEventType.UPDATE
            # Optional: Log if timestamp is older despite content change
            if kobj.manifest and prev_bundle.manifest and kobj.manifest.timestamp <= prev_bundle.manifest.timestamp:
                logger.warning(f"Incoming manifest for {kobj.rid} (GitHubEvent) has newer content (hash differs) "
                               f"but older/same timestamp ({kobj.manifest.timestamp} <= {prev_bundle.manifest.timestamp}). "
                               f"Proceeding as UPDATE based on hash.")
    else: # prev_bundle is None (not in cache or cache read failed)
        logger.info(f"GitHubEvent RID {kobj.rid} unknown or cache error. Labeling manifest as NEW.")
        kobj.normalized_event_type = KoiEventType.NEW
    return kobj


@node.processor.register_handler(HandlerType.Bundle, rid_types=[GitHubEvent])
def github_event_bundle_handler(processor: ProcessorInterface, kobj: KnowledgeObject) -> KnowledgeObject | None:
    """
    Custom bundle handler for incoming GitHubEvent bundles.
    Currently, it primarily logs information based on the event content.
    """
    logger.debug(f"GitHubEvent Bundle Handler processing bundle for RID: {kobj.rid} (Normalized KOI Event Type: {kobj.normalized_event_type})")

    if isinstance(kobj.rid, GitHubEvent) and kobj.contents:
        webhook_event_type = kobj.contents.get("webhook_event_type", "N/A")
        original_action = kobj.contents.get("action", "N/A") # e.g. for issues, pull_request
        payload_preview = str(kobj.contents.get("payload", {}))[:200] # Preview of the actual payload

        logger.info(f"Processing GitHubEvent Bundle: RID={kobj.rid}, "
                    f"WebhookEventType='{webhook_event_type}', Action='{original_action}', "
                    f"PayloadPreview='{payload_preview}...', KoiEventType='{kobj.normalized_event_type}'")
    return kobj

logger.info("GitHub specific KOI-net processor handlers (coordinator_contact, github_event_manifest, github_event_bundle) registered.")

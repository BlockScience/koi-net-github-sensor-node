import structlog
from rid_lib.types import KoiNetNode
from koi_net.processor.context import HandlerContext
from koi_net.processor.handler import HandlerType, KnowledgeHandler, STOP_CHAIN
from koi_net.processor.knowledge_object import KnowledgeObject
from koi_net_shared import GithubRepo
from .models import GithubRepoObject

log = structlog.stdlib.get_logger()


@KnowledgeHandler.create(
    HandlerType.Network,
    rid_types=[KoiNetNode],
)
def suppress_peer_node_rebroadcast(ctx: HandlerContext, kobj: KnowledgeObject):
    """Prevent forwarding other nodes' identity events.

    If the node event did not originate from this node, stop the network handler
    chain to avoid rebroadcast loops.
    """

    if kobj.source and kobj.source != ctx.identity.rid:
        return STOP_CHAIN

@KnowledgeHandler.create(
    HandlerType.Bundle,
    rid_types=[GithubRepo]
)
def github_bundle_handler(ctx: HandlerContext, kobj: KnowledgeObject):
    """Validate GithubRepo bundles."""
    try:
        GithubRepoObject.model_validate(kobj.contents or {})
    except Exception as e:
        log.warning("Invalid GithubRepoObject payload for %s: %s", kobj.rid, e)
        return STOP_CHAIN
    
    # Simple pass-through logging
    log.info("Processed GithubRepo bundle: %s", kobj.rid)


# Export handlers for GithubSensorNode class
PREPEND_HANDLERS = [
    suppress_peer_node_rebroadcast,
]

APPEND_HANDLERS = [
    github_bundle_handler,
]

# Default export keeps local ordering; core will splice around FullNode handlers
knowledge_handlers = PREPEND_HANDLERS + APPEND_HANDLERS

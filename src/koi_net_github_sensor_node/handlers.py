from dataclasses import dataclass
from typing import Any, TypeAlias

import structlog
from koi_net.components import (
    Cache,
    EventQueue,
    KobjQueue,
    NetworkGraph,
    NetworkResolver,
    NodeIdentity,
    RequestHandler,
)
from koi_net.components.interfaces import HandlerType, KnowledgeHandler, STOP_CHAIN
from koi_net.protocol.knowledge_object import KnowledgeObject
from rid_lib.types import GithubRepo, KoiNetNode

from .models import GithubRepoObject

log = structlog.stdlib.get_logger()


@dataclass
class NodeHandler(KnowledgeHandler):
    identity: NodeIdentity
    cache: Cache
    config: Any
    event_queue: EventQueue
    kobj_queue: KobjQueue
    request_handler: RequestHandler
    resolver: NetworkResolver
    graph: NetworkGraph


@dataclass
class PrependNodeHandler(NodeHandler):
    def __post_init__(self):
        super().__post_init__()
        if self in self.pipeline.knowledge_handlers:
            self.pipeline.knowledge_handlers.remove(self)
        self.pipeline.knowledge_handlers.insert(0, self)


HandlerContext: TypeAlias = NodeHandler


def suppress_peer_node_rebroadcast(ctx: HandlerContext, kobj: KnowledgeObject):
    """Prevent forwarding other nodes' identity events."""
    if kobj.source and kobj.source != ctx.identity.rid:
        return STOP_CHAIN


def github_bundle_handler(ctx: HandlerContext, kobj: KnowledgeObject):
    """Validate GithubRepo bundles."""
    try:
        GithubRepoObject.model_validate(kobj.contents or {})
    except Exception as e:
        log.warning("Invalid GithubRepoObject payload for %s: %s", kobj.rid, e)
        return STOP_CHAIN

    log.info("Processed GithubRepo bundle: %s", kobj.rid)


def logging_handler(ctx: HandlerContext, kobj: KnowledgeObject):
    """Log processed knowledge objects."""
    log.info("Processed %s: %s", type(kobj.rid).__name__, kobj.rid)


@dataclass
class SuppressPeerNodeRebroadcastHandler(PrependNodeHandler):
    handler_type = HandlerType.Network
    rid_types = (KoiNetNode,)

    def handle(self, kobj: KnowledgeObject):
        return suppress_peer_node_rebroadcast(self, kobj)


@dataclass
class GithubBundleHandler(NodeHandler):
    handler_type = HandlerType.Bundle
    rid_types = (GithubRepo,)

    def handle(self, kobj: KnowledgeObject):
        return github_bundle_handler(self, kobj)


@dataclass
class GithubLoggingHandler(NodeHandler):
    handler_type = HandlerType.Final
    rid_types = (GithubRepo,)

    def handle(self, kobj: KnowledgeObject):
        return logging_handler(self, kobj)


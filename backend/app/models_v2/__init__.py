"""commerce_ops V2 model registry."""

from backend.app.models_v2.catalog import (
    CategoryV2,
    ProductCategoryV2,
    ProductV2,
    ProductVariantV2,
)
from backend.app.models_v2.operations import (
    IncomingShipmentV2,
    InventoryMovementV2,
    InventorySnapshotV2,
    LaunchIncomingDependencyV2,
    LaunchProductV2,
    LaunchScheduleV2,
    OrderItemV2,
    OrderV2,
    ReservationV2,
    TaskDependencyV2,
    TaskIncomingDependencyV2,
    TaskReviewV2,
    TaskV2,
)

from backend.app.models_v2.integrations import (
    ExternalAccountV2,
    IncomingEventV2,
    ProcessedActionV2,
    ProductExternalMappingV2,
    SyncStatusV2,
    VariantExternalMappingV2,
)
from backend.app.models_v2.ai import (
    AgentRunV2,
    ConversationV2,
    MessageContextV2,
    MessageV2,
    RagChunkV2,
)
from backend.app.models_v2.tenant import TenantV2

__all__ = [
    "TenantV2",
    "ProductV2",
    "CategoryV2",
    "ProductCategoryV2",
    "ProductVariantV2",
    "OrderV2",
    "OrderItemV2",
    "InventorySnapshotV2",
    "InventoryMovementV2",
    "IncomingShipmentV2",
    "ReservationV2",
    "TaskV2",
    "TaskDependencyV2",
    "TaskIncomingDependencyV2",
    "TaskReviewV2",
    "LaunchScheduleV2",
    "LaunchProductV2",
    "LaunchIncomingDependencyV2",
    "ExternalAccountV2",
    "ProductExternalMappingV2",
    "VariantExternalMappingV2",
    "SyncStatusV2",
    "IncomingEventV2",
    "ProcessedActionV2",
    "RagChunkV2",
    "ConversationV2",
    "MessageV2",
    "MessageContextV2",
    "AgentRunV2",
]
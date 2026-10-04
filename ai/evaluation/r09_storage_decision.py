from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai.evaluation.r09_graph_eval_contract import (
    R09_EMBEDDING_CONFIG,
)


class VectorPersistenceDecision(str, Enum):
    DEFER_VECTOR_PERSISTENCE = "DEFER_VECTOR_PERSISTENCE"
    ENABLE_PGVECTOR_FOR_R09 = "ENABLE_PGVECTOR_FOR_R09"


@dataclass(frozen=True)
class R09StorageDecision:
    decision: VectorPersistenceDecision

    embedding_model: str
    embedding_revision: str
    vector_dimension: int
    normalized: bool

    retrieval_runtime: str
    rag_chunk_storage: str

    pgvector_enabled: bool
    vector_column_required_now: bool
    vector_writer_required_now: bool

    reason: str

    corpus_scope: str
    writer_contract: str
    restart_readback_condition: str
    approval_boundary: str


R09_STORAGE_DECISION = R09StorageDecision(
    decision=VectorPersistenceDecision.DEFER_VECTOR_PERSISTENCE,

    embedding_model=R09_EMBEDDING_CONFIG.model,
    embedding_revision=R09_EMBEDDING_CONFIG.revision,
    vector_dimension=R09_EMBEDDING_CONFIG.dimension,
    normalized=R09_EMBEDDING_CONFIG.normalized,

    retrieval_runtime="EXISTING_IN_MEMORY_DENSE_INDEX",

    rag_chunk_storage=(
        "SOURCE_VERSION_TEXT_HASH_AND_EMBEDDING_METADATA_ONLY"
    ),

    pgvector_enabled=False,
    vector_column_required_now=False,
    vector_writer_required_now=False,

    reason=(
        "R09-PRE confirmed that V2 RagChunkV2 contains source/version/"
        "chunk text/hash and embedding metadata fields, while no pgvector "
        "extension, vector column, vector writer, or vector retrieval runtime "
        "is currently implemented. R09 E05 can reuse the existing in-memory "
        "DenseIndex, so persistent vector storage is deferred until runtime "
        "need is demonstrated."
    ),

    corpus_scope=(
        "APPROVED_SYNTHETIC_OR_PURPOSE_SCOPED_SAFE_ARTIFACTS_ONLY"
    ),

    writer_contract=(
        "NO_WRITER_IN_R09_PRE; future writer must validate "
        "source/version/content_hash/model_revision/dimension/normalization "
        "before persistence"
    ),

    restart_readback_condition=(
        "WHEN_VECTOR_PERSISTENCE_IS_INTRODUCED_VERIFY_SAME_CORPUS_VERSION_"
        "AND_MODEL_METADATA_AFTER_PROCESS_RESTART"
    ),

    approval_boundary=(
        "NEW_ACTUAL_DATA_REQUIRES_EXISTING_SAME_PURPOSE_SAME_HASH_APPROVAL_"
        "OR_BACKEND_PROJECTION_USER_REVIEW_PURPOSE_HASH_APPROVAL"
    ),
)
from ai.evaluation.r09_storage_decision import (
    R09_STORAGE_DECISION,
    VectorPersistenceDecision,
)


def test_r09_vector_persistence_is_deferred():
    assert (
        R09_STORAGE_DECISION.decision
        == VectorPersistenceDecision.DEFER_VECTOR_PERSISTENCE
    )

    assert R09_STORAGE_DECISION.pgvector_enabled is False
    assert R09_STORAGE_DECISION.vector_column_required_now is False
    assert R09_STORAGE_DECISION.vector_writer_required_now is False


def test_r09_reuses_existing_embedding_config():
    assert (
        R09_STORAGE_DECISION.embedding_model
        == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    assert (
        R09_STORAGE_DECISION.embedding_revision
        == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    )

    assert R09_STORAGE_DECISION.vector_dimension == 384
    assert R09_STORAGE_DECISION.normalized is True


def test_r09_uses_existing_in_memory_dense_runtime():
    assert (
        R09_STORAGE_DECISION.retrieval_runtime
        == "EXISTING_IN_MEMORY_DENSE_INDEX"
    )


def test_r09_does_not_claim_vector_storage_complete():
    assert (
        R09_STORAGE_DECISION.rag_chunk_storage
        == "SOURCE_VERSION_TEXT_HASH_AND_EMBEDDING_METADATA_ONLY"
    )

    assert "pgvector" in R09_STORAGE_DECISION.reason
    assert "deferred" in R09_STORAGE_DECISION.reason.lower()

def test_r09_corpus_scope_is_approval_bounded():
    assert (
        R09_STORAGE_DECISION.corpus_scope
        == "APPROVED_SYNTHETIC_OR_PURPOSE_SCOPED_SAFE_ARTIFACTS_ONLY"
    )

    assert "APPROVAL" in R09_STORAGE_DECISION.approval_boundary


def test_r09_writer_and_restart_contract_are_deferred_but_explicit():
    assert "NO_WRITER_IN_R09_PRE" in R09_STORAGE_DECISION.writer_contract

    assert (
        "PROCESS_RESTART"
        in R09_STORAGE_DECISION.restart_readback_condition
    )

    assert R09_STORAGE_DECISION.pgvector_enabled is False
    assert R09_STORAGE_DECISION.vector_writer_required_now is False
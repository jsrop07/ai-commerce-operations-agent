"""C16 persistent pgvector embeddings for safe RAG chunks.

Revision ID: c16e20261006
Revises: 8dba0e0a9dbd
"""

from alembic import op

revision = "c16e20261006"
down_revision = "8dba0e0a9dbd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE ai.rag_chunks ADD COLUMN embedding vector(384)")
    op.execute(
        "CREATE INDEX ix_ai_rag_chunks_embedding_cosine_hnsw "
        "ON ai.rag_chunks USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL AND is_current = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ai.ix_ai_rag_chunks_embedding_cosine_hnsw")
    op.execute("ALTER TABLE ai.rag_chunks DROP COLUMN embedding")

"""Read-only C16 Product evidence lookup for a frozen C09 identity."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from sqlalchemy import literal_column, select
from sqlalchemy.orm import Session

from backend.app.models_v2.ai import RagChunkV2
from backend.app.models_v2.catalog import ProductV2


@dataclass(frozen=True)
class ProductRetrievalEvidence:
    source_type: str
    source_id: str
    source_version: str
    chunk_no: int
    product_code: str
    product_name: str
    method: str = "EXACT_PRODUCT_ID"
    rank: int = 1
    score: float | None = None

    @property
    def evidence_id(self) -> str:
        return f"rag:{self.source_type}:{self.source_id}:{self.source_version}:{self.chunk_no}"

    def metadata(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "chunk_no": self.chunk_no,
            "method": self.method,
            "rank": self.rank,
            "score": self.score,
        }


def retrieve_frozen_product_evidence(
    session: Session, *, tenant_id: UUID, product_id: UUID,
) -> ProductRetrievalEvidence | None:
    """Require one current, embedded Product chunk for the exact owned V2 Product."""
    product = session.scalar(select(ProductV2).where(
        ProductV2.tenant_id == tenant_id, ProductV2.id == product_id,
    ))
    if product is None:
        return None
    rows = session.execute(
        select(RagChunkV2, literal_column("embedding").is_not(None))
        .where(
            RagChunkV2.tenant_id == tenant_id,
            RagChunkV2.source_type == "PRODUCT",
            RagChunkV2.source_id == str(product_id),
            RagChunkV2.chunk_no == 0,
            RagChunkV2.is_current.is_(True),
        ).limit(2)
    ).all()
    if len(rows) != 1:
        return None
    chunk, has_embedding = rows[0]
    metadata = chunk.metadata_json
    if (
        not has_embedding
        or not isinstance(metadata, dict)
        or metadata.get("data_mode") != "SYNTHETIC_DEMO"
        or metadata.get("product_code") != product.product_code
        or not chunk.source_version
        or chunk.content_hash != sha256(chunk.chunk_text.encode("utf-8")).hexdigest()
    ):
        return None
    return ProductRetrievalEvidence(
        source_type="PRODUCT", source_id=str(product.id),
        source_version=chunk.source_version, chunk_no=chunk.chunk_no,
        product_code=product.product_code, product_name=product.product_name,
    )

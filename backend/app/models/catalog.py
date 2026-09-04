"""D02-BE-01 tenant-aware catalog models."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, IdentityMixin, TenantMixin, VersionedMixin


class Tenant(Base, IdentityMixin, VersionedMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")


class ProviderAccount(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "provider_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "account_ref"),)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    capability: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    credential_ref: Mapped[str | None] = mapped_column(String(255))


class Brand(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canonical_name"),
        UniqueConstraint("tenant_id", "id"),
    )

    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class Product(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "brand_id"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "brand_id"],
            ["brands.tenant_id", "brands.id"],
            name="fk_products_brand_same_tenant",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str | None] = mapped_column(String(32))
    player_count: Mapped[str | None] = mapped_column(String(32))
    play_time: Mapped[int | None]
    difficulty: Mapped[float | None] = mapped_column(Float)
    brand: Mapped[Brand] = relationship()


class SKU(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "skus"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canonical_code"),
        UniqueConstraint("tenant_id", "barcode"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_skus_product_same_tenant",
        ),
    )

    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    canonical_code: Mapped[str] = mapped_column(String(120), nullable=False)
    option: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    product: Mapped[Product] = relationship()


class ProviderMapping(Base, IdentityMixin, TenantMixin, VersionedMixin):
    __tablename__ = "provider_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "object_type", "external_id", "version"),
        CheckConstraint(
            "NOT (status = 'AMBIGUOUS' AND approved = true)",
            name="ck_ambiguous_mapping_not_approved",
        ),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_id: Mapped[str | None] = mapped_column(String(36))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

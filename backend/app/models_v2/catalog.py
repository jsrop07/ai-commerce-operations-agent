"""V2 catalog models."""

from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    func
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base_v2 import (
    BaseV2,
    TenantV2Mixin,
    TimestampV2Mixin,
    UUIDIdentityMixin,
)


class ProductV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_catalog_products_tenant_id_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "cafe24_product_no",
            name="uq_catalog_products_tenant_cafe24_product_no",
        ),
        UniqueConstraint(
            "tenant_id",
            "product_code",
            name="uq_catalog_products_tenant_product_code",
        ),
        {"schema": "catalog"},
    )

    cafe24_product_no: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    product_code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    custom_product_code: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    sale_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    display_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    selling_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    sold_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    operational: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    source_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class CategoryV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_catalog_categories_tenant_id_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "cafe24_category_no",
            name="uq_catalog_categories_tenant_cafe24_category_no",
        ),
        CheckConstraint(
            "category_depth >= 0",
            name="ck_catalog_categories_depth_nonnegative",
        ),
        CheckConstraint(
            "parent_category_id IS NULL OR parent_category_id <> id",
            name="ck_catalog_categories_no_self_parent",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_category_id"],
            ["catalog.categories.tenant_id", "catalog.categories.id"],
            name="fk_catalog_categories_parent_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "catalog"},
    )

    cafe24_category_no: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    category_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    parent_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    category_depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ProductCategoryV2(BaseV2):
    __tablename__ = "product_categories"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "product_id",
            "category_id",
            name="pk_catalog_product_categories",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_catalog_product_categories_product_same_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "category_id"],
            ["catalog.categories.tenant_id", "catalog.categories.id"],
            name="fk_catalog_product_categories_category_same_tenant",
            ondelete="CASCADE",
        ),
        {"schema": "catalog"},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProductVariantV2(
    UUIDIdentityMixin,
    TenantV2Mixin,
    TimestampV2Mixin,
    BaseV2,
):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_catalog_product_variants_tenant_id_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["catalog.products.tenant_id", "catalog.products.id"],
            name="fk_catalog_product_variants_product_same_tenant",
            ondelete="RESTRICT",
        ),
        {"schema": "catalog"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    variant_code: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    option_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    barcode: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    variant_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
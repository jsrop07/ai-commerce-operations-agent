import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models.catalog import SKU, Brand, Product, ProviderMapping, Tenant


def test_tenant_scoped_catalog_uniqueness_and_ambiguous_mapping() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Tenant(id="tenant-a", name="A", environment="TEST", status="ACTIVE"),
                Tenant(id="tenant-b", name="B", environment="TEST", status="ACTIVE"),
                Brand(tenant_id="tenant-a", canonical_name="Synthetic Brand", aliases=[]),
                Brand(tenant_id="tenant-b", canonical_name="Synthetic Brand", aliases=[]),
            ]
        )
        session.commit()
        assert session.query(Brand).count() == 2
        session.add(
            ProviderMapping(
                tenant_id="tenant-a",
                provider="TOSS_POS",
                object_type="SKU",
                external_id="external-1",
                canonical_id=None,
                confidence=0.4,
                status="AMBIGUOUS",
                approved=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_provider_mapping_external_id_is_scoped_by_tenant() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                Tenant(id="tenant-a", name="A", environment="TEST", status="ACTIVE"),
                Tenant(id="tenant-b", name="B", environment="TEST", status="ACTIVE"),
            ]
        )
        session.commit()

        session.add_all(
            [
                ProviderMapping(
                    tenant_id="tenant-a",
                    provider="CAFE24",
                    object_type="SKU",
                    external_id="shared-external-1",
                    canonical_id="sku-a",
                    confidence=1.0,
                    status="VERIFIED",
                    approved=True,
                    version=1,
                ),
                ProviderMapping(
                    tenant_id="tenant-b",
                    provider="CAFE24",
                    object_type="SKU",
                    external_id="shared-external-1",
                    canonical_id="sku-b",
                    confidence=1.0,
                    status="VERIFIED",
                    approved=True,
                    version=1,
                ),
            ]
        )

        session.commit()

        assert session.query(ProviderMapping).count() == 2


def test_sku_product_relationship_is_tenant_scoped_in_metadata() -> None:
    sku_table = SKU.__table__

    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in sku_table.foreign_key_constraints
    }

    assert (
        ("tenant_id", "product_id"),
        ("products.tenant_id", "products.id"),
    ) in foreign_keys

    product_foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in Product.__table__.foreign_key_constraints
    }
    assert (
        ("tenant_id", "brand_id"),
        ("brands.tenant_id", "brands.id"),
    ) in product_foreign_keys

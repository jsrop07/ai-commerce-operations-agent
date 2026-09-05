from backend.app.worker.normalizers.provider_normalizer import (
    normalize_cafe24_product_export,
)


def test_cafe24_product_export_normalizes_selected_fields() -> None:
    row = {
        "상품코드": "P001",
        "자체 상품코드": "BG-001",
        "상품명": "테스트 보드게임",
        "영문 상품명": "Test Board Game",
        "브랜드": "B001",
        "브랜드명": "테스트브랜드",
        "판매가": "39,000",
        "소비자가": "45,000",
        "HS코드": "9504",
    }

    result = normalize_cafe24_product_export(row)

    assert result.status == "NORMALIZED"
    assert result.identity == "P001"
    assert result.canonical is not None

    assert result.canonical["provider_product_id"] == "P001"
    assert result.canonical["external_sku_candidate"] == "BG-001"
    assert result.canonical["name"] == "테스트 보드게임"
    assert result.canonical["sale_price"] == "39000"
    assert result.canonical["retail_price"] == "45000"


def test_unknown_cafe24_field_is_preserved() -> None:
    row = {
        "상품코드": "P001",
        "상품명": "테스트 보드게임",
        "HS코드": "9504",
        "미래에추가된필드": "SOURCE_VALUE",
    }

    result = normalize_cafe24_product_export(row)

    assert result.status == "NORMALIZED"
    assert result.unknown["HS코드"] == "9504"
    assert result.unknown["미래에추가된필드"] == "SOURCE_VALUE"


def test_missing_cafe24_product_code_is_quarantined() -> None:
    result = normalize_cafe24_product_export(
        {
            "상품코드": "",
            "상품명": "테스트 상품",
        }
    )

    assert result.status == "QUARANTINED"
    assert result.reason == "MISSING_PRODUCT_CODE"
    assert result.canonical is None


def test_missing_cafe24_product_name_is_quarantined() -> None:
    result = normalize_cafe24_product_export(
        {
            "상품코드": "P001",
            "상품명": "",
        }
    )

    assert result.status == "QUARANTINED"
    assert result.reason == "MISSING_PRODUCT_NAME"
    assert result.canonical is None
from dataclasses import dataclass


@dataclass(frozen=True)
class StructuredChunk:
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    chunk_index: int
    structure_type: str
    text: str
    field_path: str


def chunk_product_record(
    record: dict,
) -> list[StructuredChunk]:
    fields = record.get("fields")

    if not isinstance(fields, dict):
        raise ValueError(
            "PRODUCT record requires fields"
        )

    parts: list[str] = []

    for field_name in (
        "name",
        "category",
        "language",
        "description",
        "components",
        "compatibility",
    ):
        value = fields.get(field_name)

        if value:
            parts.append(
                f"{field_name}: {value}"
            )

    if not parts:
        raise ValueError(
            "PRODUCT fields contain no usable content"
        )

    text = "\n".join(parts)

    return [
        StructuredChunk(
            chunk_id=(
                f"{record['source_id']}:"
                f"{record['version']}:"
                "structured:product:0"
            ),
            source_id=record["source_id"],
            source_type=record["source_type"],
            version=record["version"],
            chunk_index=0,
            structure_type="PRODUCT_RECORD",
            text=text,
            field_path="fields",
        )
    ]


def chunk_policy_paragraphs(
    record: dict,
) -> list[StructuredChunk]:
    paragraphs = record.get("paragraphs")

    if not isinstance(paragraphs, list):
        raise ValueError(
            "POLICY record requires paragraphs"
        )

    chunks: list[StructuredChunk] = []

    for index, paragraph in enumerate(
        paragraphs
    ):
        heading = paragraph.get(
            "heading",
            "",
        ).strip()

        text = paragraph.get(
            "text",
            "",
        ).strip()

        if not text:
            continue

        combined = (
            f"{heading}\n{text}"
            if heading
            else text
        )

        chunks.append(
            StructuredChunk(
                chunk_id=(
                    f"{record['source_id']}:"
                    f"{record['version']}:"
                    f"structured:policy:{index}"
                ),
                source_id=record["source_id"],
                source_type=record["source_type"],
                version=record["version"],
                chunk_index=index,
                structure_type="POLICY_PARAGRAPH",
                text=combined,
                field_path=(
                    f"paragraphs[{index}]"
                ),
            )
        )

    return chunks


def chunk_faq_pairs(
    record: dict,
) -> list[StructuredChunk]:
    faq = record.get("faq")

    if not isinstance(faq, list):
        raise ValueError(
            "FAQ record requires faq list"
        )

    chunks: list[StructuredChunk] = []

    for index, item in enumerate(faq):
        question = item.get(
            "question",
            "",
        ).strip()

        answer = item.get(
            "answer",
            "",
        ).strip()

        if not question or not answer:
            continue

        text = (
            f"question: {question}\n"
            f"answer: {answer}"
        )

        chunks.append(
            StructuredChunk(
                chunk_id=(
                    f"{record['source_id']}:"
                    f"{record['version']}:"
                    f"structured:faq:{index}"
                ),
                source_id=record["source_id"],
                source_type=record["source_type"],
                version=record["version"],
                chunk_index=index,
                structure_type="FAQ_PAIR",
                text=text,
                field_path=f"faq[{index}]",
            )
        )

    return chunks


def chunk_structured(
    record: dict,
) -> list[StructuredChunk]:
    if record["source_type"] == "PRODUCT":
        return chunk_product_record(record)

    if "faq" in record:
        return chunk_faq_pairs(record)

    if record["source_type"] == "POLICY":
        return chunk_policy_paragraphs(
            record
        )

    raise ValueError(
        f"Unsupported source_type: "
        f"{record['source_type']}"
    )


def chunk_records_structured(
    records: list[dict],
) -> list[StructuredChunk]:
    chunks: list[StructuredChunk] = []

    for record in records:
        chunks.extend(
            chunk_structured(record)
        )

    return chunks
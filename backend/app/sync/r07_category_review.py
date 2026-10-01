from pathlib import Path

from backend.app.sync.day09_ai_catalog_handoff import (
    _latest_by_identity,
    _load_observations,
)


PROTECTED_ROOT = Path(r"C:\ai-commerce-private\cafe24\cafe24")
OUTPUT_PATH = Path(
    r"artifacts\experiments\OPS-R07-PRE\private\product\review\category_safe_review.csv"
)


def main() -> None:
    sanitized_root = PROTECTED_ROOT / "sanitized"

    observations, _ = _load_observations(
        sanitized_root / "categories",
        preferred_glob="category-full-*.sanitized.json",
    )

    categories = _latest_by_identity(
        observations,
        identity_field="category_no",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        f.write("category_no,category_name\n")

        for category_no, observation in sorted(categories.items()):
            category_name = str(
                observation.record.get("category_name") or ""
            ).replace('"', '""')

            f.write(f'{category_no},"{category_name}"\n')

    print("CATEGORY_COUNT=", len(categories))
    print("OUTPUT=", OUTPUT_PATH)


if __name__ == "__main__":
    main()
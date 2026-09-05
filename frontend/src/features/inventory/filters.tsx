export interface InventoryFilterValue {
  brand: string;
  category: string;
}

interface InventoryFiltersProps {
  value: InventoryFilterValue;
  brands: string[];
  categories: string[];
  onChange: (value: InventoryFilterValue) => void;
}

export default function InventoryFilters({
  value,
  brands,
  categories,
  onChange,
}: InventoryFiltersProps) {
  return (
    <section
      className="inventory-filters"
      aria-label="재고 필터"
    >
      <label>
        브랜드
        <select
          aria-label="브랜드 필터"
          value={value.brand}
          onChange={(event) =>
            onChange({
              ...value,
              brand: event.target.value,
            })
          }
        >
          <option value="">전체</option>

          {brands.map((brand) => (
            <option
              key={brand}
              value={brand}
            >
              {brand}
            </option>
          ))}
        </select>
      </label>

      <label>
        카테고리
        <select
          aria-label="카테고리 필터"
          value={value.category}
          onChange={(event) =>
            onChange({
              ...value,
              category: event.target.value,
            })
          }
        >
          <option value="">전체</option>

          {categories.map((category) => (
            <option
              key={category}
              value={category}
            >
              {category}
            </option>
          ))}
        </select>
      </label>

      <label>
        언어
        <select
          aria-label="언어 필터"
          aria-describedby="inventory-unsupported-filter-description"
          disabled
        >
          <option>계약 미제공</option>
        </select>
      </label>

      <label>
        관계
        <select
          aria-label="관계 필터"
          aria-describedby="inventory-unsupported-filter-description"
          disabled
        >
          <option>계약 미제공</option>
        </select>
      </label>

      <label>
        위험
        <select
          aria-label="위험 필터"
          aria-describedby="inventory-unsupported-filter-description"
          disabled
        >
          <option>계약 미제공</option>
        </select>
      </label>

      <p
        id="inventory-unsupported-filter-description"
        className="inventory-filter-note muted"
      >
        언어·관계·위험 필터는 현재 계약에서 제공되지 않습니다.
      </p>
    </section>
  );
}

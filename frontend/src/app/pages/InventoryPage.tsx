import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import InventoryFilters, {
  type InventoryFilterValue,
} from "../../features/inventory/filters";
import InventoryDetailPanel from "../../features/inventory/InventoryDetailPanel";
import { SourceBadge } from "../../components/Badges";
import FreshnessLabel from "../../components/FreshnessLabel";
import SystemState from "../../components/SystemStates";
import { mockApiGet } from "../../mocks/handlers";
import type {
  ApiEnvelope,
  InventorySnapshot,
  ProductSummary,
  SkuSummary,
  TaskSummary,
} from "../../types/contracts";
import { getDay08Inventory } from "../../api/day08";
import CatalogBrowser from "../../features/catalog/CatalogBrowser";
export { CatalogPagination } from "../../features/catalog/CatalogBrowser";
import QualityStatus from "../../features/integrations/QualityStatus";

interface ProductCatalogData {
  products: ProductSummary[];
  skus: SkuSummary[];
}

const freshnessOrder = {
  STALE: 0,
  UNKNOWN: 1,
  FRESH: 2,
} as const;

function sortInventory(
  items: InventorySnapshot[],
): InventorySnapshot[] {
  return [...items].sort((a, b) => {
    const freshnessDiff =
      freshnessOrder[a.freshness] -
      freshnessOrder[b.freshness];

    if (freshnessDiff !== 0) {
      return freshnessDiff;
    }

    const skuDiff = a.sku_id.localeCompare(b.sku_id);

    if (skuDiff !== 0) {
      return skuDiff;
    }

    return a.provider.localeCompare(b.provider);
  });
}
function displayNullableNumber(
  value: number | null | undefined,
): string {
  return value === null || value === undefined
    ? "미제공"
    : String(value);
}

function displayRiskLevel(
  value: InventorySnapshot["risk_level"],
): string {
  return value ?? "미제공";
}

function InventorySnapshotSection() {
  const usingBackend = import.meta.env.VITE_USE_REAL_BACKEND === "true";
  const [inventory, setInventory] =
    useState<ApiEnvelope<InventorySnapshot[]> | null>(null);
  const [catalog, setCatalog] =
    useState<ApiEnvelope<ProductCatalogData> | null>(null);
  const [tasks, setTasks] =
    useState<ApiEnvelope<TaskSummary[]> | null>(null);

  const [filters, setFilters] =
    useState<InventoryFilterValue>({
      brand: "",
      category: "",
    });

  const [filtersOpen, setFiltersOpen] = useState(false);
  
  const [selectedInventory, setSelectedInventory] =
    useState<InventorySnapshot | null>(null);

  const lastSelectedRowRef =
    useRef<HTMLTableRowElement | null>(null);
  const restoreFocusOnCloseRef = useRef(false);

  const closeInventoryDetail = useCallback(() => {
    restoreFocusOnCloseRef.current = true;
    setSelectedInventory(null);
  }, []);
  
  const [inventoryError, setInventoryError] =
    useState<string | null>(null);
  
    useLayoutEffect(() => {
    if (
      selectedInventory !== null ||
      !restoreFocusOnCloseRef.current
    ) {
      return;
    }

    restoreFocusOnCloseRef.current = false;
    lastSelectedRowRef.current?.focus();
  }, [selectedInventory]);

  useEffect(() => {
    let active = true;

    if (!usingBackend) mockApiGet<ApiEnvelope<TaskSummary[]>>(
      "/api/v1/tasks",
    ).then((response) => {
      if (active) setTasks(response);
    });

    getDay08Inventory()
      .then((response) => {
        if (active) {
          setInventory(response);
          setInventoryError(null);
        }
      })
      .catch(() => {
        if (active) {
          setInventoryError(
            "재고 Backend Projection을 불러오지 못했습니다.",
          );
        }
      });

    if (!usingBackend) mockApiGet<ApiEnvelope<ProductCatalogData>>(
      "/api/v1/products",
    ).then((response) => {
      if (active) setCatalog(response);
    });

    return () => {
      active = false;
    };
  }, [usingBackend]);

  if (inventoryError) {
    return (
      <div
        className="inventory-snapshot-content"
      >
        <SystemState
          state="denied"
          title="재고 데이터를 불러오지 못했습니다"
          description={inventoryError}
        />
      </div>
    );
  }
  if (!inventory || (!usingBackend && (!catalog || !tasks))) {
    return (
      <div
        className="inventory-snapshot-content"
      >
        <SystemState state="loading" />
      </div>
    );
  }

  const catalogData = catalog?.data ?? { products: [], skus: [] };
  const inventoryTaskProposals = (tasks?.data ?? []).filter(
      (task) =>
        task.type === "INVENTORY_REVIEW" &&
        task.status === "PROPOSED",
    );

  const { data } = inventory;
  const skuById = new Map(
    catalogData.skus.map((sku) => [
      sku.id,
      sku,
    ]),
  );

  const productById = new Map(
    catalogData.products.map((product) => [
      product.id,
      product,
    ]),
  );

  const brands = Array.from(
    new Set(
      catalogData.products.map(
        (product) => product.brand_id,
      ),
    ),
  ).sort();

  const filteredInventory = usingBackend ? data : data.filter((item) => {
    const sku = skuById.get(item.sku_id);

    if (!sku) {
      return false;
    }

    const product = productById.get(
      sku.product_id,
    );

    if (!product) {
      return false;
    }

    const brandMatches =
      filters.brand === "" ||
      product.brand_id === filters.brand;

    const categoryMatches =
      filters.category === "" ||
      product.category === filters.category;

    return brandMatches && categoryMatches;
  });

  const categories = Array.from(
    new Set(
      catalogData.products.map(
        (product) => product.category,
      ),
    ),
  ).sort();

  const sortedInventory =
    sortInventory(filteredInventory);

  const staleCount = filteredInventory.filter(
    (item) => item.freshness === "STALE",
  ).length;

  function selectInventory(
    item: InventorySnapshot,
    row: HTMLTableRowElement,
  ) {
    const isSameItem =
      selectedInventory?.provider === item.provider &&
      selectedInventory?.sku_id === item.sku_id;

    if (isSameItem) {
      closeInventoryDetail();
      return;
    }

    restoreFocusOnCloseRef.current = false;
    lastSelectedRowRef.current = row;
    setSelectedInventory(item);
  }

  if (data.length === 0) {
    return (
      <div
        className="inventory-snapshot-content"
      >
        <SystemState
          state="empty"
          title="표시할 재고가 없습니다"
          description="현재 조회 가능한 재고 Snapshot이 없습니다."
        />
      </div>
    );
  }

  return (
    <div
      className="inventory-snapshot-content"
    >

      <div className="inventory-filter-area">
        <div className="inventory-filter-topline">
          <button
            type="button"
            className="inventory-filter-toggle"
            aria-expanded={filtersOpen}
            aria-controls="inventory-filter-panel"
            onClick={() => setFiltersOpen((current) => !current)}
          >
            <span>필터</span>
            <span aria-hidden="true">{filtersOpen ? "⌃" : "⌄"}</span>
          </button>

          <span className="inventory-query-time">
            조회 기준{" "}
            <time dateTime={inventory.as_of}>
              {new Date(inventory.as_of).toLocaleString("ko-KR")}
            </time>
          </span>
        </div>

        <div
          id="inventory-filter-panel"
          className="inventory-filter-panel"
          hidden={!filtersOpen}
        >
          <InventoryFilters
            value={filters}
            brands={brands}
            categories={categories}
            onChange={setFilters}
          />
        </div>
      </div>

      <details className="inventory-safety-notice">
        <summary>
          <span className="inventory-safety-notice-heading">
            재고 데이터 확인 안내
          </span>

          <span className="inventory-safety-notice-summary">
            {staleCount > 0
              ? `오래된 데이터 ${staleCount}건 · 최신 재고 및 위험 판단 확인 필요`
              : "재고 수량 및 판단 기준 확인"}
          </span>

          <span className="inventory-safety-notice-action">
            상세 안내
          </span>
        </summary>

        <div className="inventory-safety-notice-detail">
          <p>
            현재 화면은 확인된 재고 Snapshot 계약의 값만 표시합니다.
            예상재고·입고예정·위험 값은 계약에 없는 값을 임의 생성하지 않습니다.
          </p>

          {staleCount > 0 && (
            <div data-testid="inventory-stale-warning" role="status">
              <strong>
                오래된 재고 데이터 {staleCount}건이 있습니다.
              </strong>
              <p>
                최신 수량을 확인하기 전에는 재고 위험을 확정하지 않습니다.
              </p>
            </div>
          )}
        </div>
      </details>

      {sortedInventory.length === 0 ? (
        <SystemState
          state="empty"
          title="조건에 맞는 재고가 없습니다"
          description="선택한 필터 조건을 변경해 다시 확인하세요."
        />
      ) : (
        <section className="card inventory-table-card">
            <table className="dense-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>채널</th>
                <th>현재 Snapshot</th>
                <th>예약</th>
                <th>예상재고</th>
                <th>입고예정</th>
                <th>위험</th>
                <th>최신성</th>
                <th>기준 시각</th>
                <th>품질 상태</th>
              </tr>
            </thead>

            <tbody>
              {sortedInventory.map((item) => (
                <tr
                  key={`${item.provider}-${item.sku_id}`}
                  tabIndex={0}
                  className={
                    selectedInventory?.provider === item.provider &&
                    selectedInventory?.sku_id === item.sku_id
                      ? "inventory-row selected"
                      : "inventory-row"
                  }
                  aria-selected={
                    selectedInventory?.provider === item.provider &&
                    selectedInventory?.sku_id === item.sku_id
                  }
                  aria-expanded={
                    selectedInventory?.provider === item.provider &&
                    selectedInventory?.sku_id === item.sku_id
                  }
                  aria-controls="inventory-detail-panel"
                  aria-label={`${item.sku_id} ${item.provider} 재고 상세 열기`}
                  onClick={(event) => {
                    selectInventory(
                      item,
                      event.currentTarget,
                    );
                  }}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" ||
                      event.key === " "
                    ) {
                      event.preventDefault();

                      selectInventory(
                        item,
                        event.currentTarget,
                      );
                    }
                  }}
                >
                  <td className="mono">
                    {item.sku_id}
                  </td>

                  <td>
                    <SourceBadge>
                      {item.provider}
                    </SourceBadge>
                  </td>

                  <td className="number">
                    {item.on_hand}
                  </td>

                  <td className="number">
                    {item.reserved}
                  </td>

                  <td className="number">
                    {displayNullableNumber(
                      item.expected_inventory,
                    )}
                  </td>

                  <td className="number">
                    {displayNullableNumber(
                      item.confirmed_incoming,
                    )}
                  </td>

                  <td>
                    {displayRiskLevel(item.risk_level)}
                  </td>

                  <td>
                    <FreshnessLabel
                      freshness={item.freshness}
                      source={item.provider}
                      asOf={item.as_of}
                      showMetadata={false}
                    />
                  </td>

                  <td>
                    <time dateTime={item.as_of}>
                      {new Date(
                        item.as_of,
                      ).toLocaleString("ko-KR")}
                    </time>
                  </td>

                  <td>
                    {item.quality_status ? (
                      <QualityStatus
                        status={item.quality_status}
                        provider={item.provider}
                        confirmedForTotal={
                          item.confirmed_for_total
                        }
                      />
                    ) : (
                      <span className="muted">
                        미제공
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      <InventoryDetailPanel
        item={selectedInventory}
        open={selectedInventory !== null}
        taskProposals={inventoryTaskProposals}
        onClose={closeInventoryDetail}
      />
    </div>
  );
}

type InventoryTab = "catalog" | "snapshot";

export default function InventoryPage() {
  const [activeTab, setActiveTab] = useState<InventoryTab>("catalog");

  return (
    <div className="page inventory-page" data-testid="route-inventory">
      <div className="inventory-page-heading">
        <h1>상품 · 재고</h1>
      </div>

      <div className="inventory-page-tabs" role="tablist" aria-label="상품·재고 보기">
        <button
          type="button"
          id="inventory-catalog-tab"
          role="tab"
          aria-selected={activeTab === "catalog"}
          aria-controls="inventory-catalog-panel"
          tabIndex={activeTab === "catalog" ? 0 : -1}
          onClick={() => setActiveTab("catalog")}
        >
          상품 목록
        </button>

        <button
          type="button"
          id="inventory-snapshot-tab"
          role="tab"
          aria-selected={activeTab === "snapshot"}
          aria-controls="inventory-snapshot-panel"
          tabIndex={activeTab === "snapshot" ? 0 : -1}
          onClick={() => setActiveTab("snapshot")}
        >
          재고 현황
        </button>
      </div>

      <section
        id="inventory-catalog-panel"
        role="tabpanel"
        aria-labelledby="inventory-catalog-tab"
        className="inventory-tab-panel"
        hidden={activeTab !== "catalog"}
      >
        <CatalogBrowser />
      </section>

      <section
        id="inventory-snapshot-panel"
        role="tabpanel"
        aria-labelledby="inventory-snapshot-tab"
        aria-label="재고 Snapshot"
        className="inventory-tab-panel"
        data-testid="inventory-snapshot-section"
        hidden={activeTab !== "snapshot"}
      >
        <InventorySnapshotSection />
      </section>
    </div>
  );
}

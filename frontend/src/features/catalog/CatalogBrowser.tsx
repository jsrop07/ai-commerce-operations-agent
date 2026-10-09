import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  getCatalogCategories,
  getCatalogProducts,
  getCatalogSummary,
  type CatalogHierarchyCategory,
  type CatalogProductsPage,
  type CatalogProductsQuery,
  type CatalogSummary,
} from "../../api/catalog";
import SystemState from "../../components/SystemStates";
import {
  catalogPageNumbers,
  readCatalogUrl,
  writeCatalogUrl,
  type CatalogSortBy,
  type CatalogUrlState,
} from "./catalogState";
import {
  useOptionalCommonAiDrawer,
} from "../../app/CommonAiDrawerContext";
const pageSize = 50;

export function CatalogPagination({
  page,
  currentPage,
  onPageChange,
}: {
  page: CatalogProductsPage;
  currentPage: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.ceil(page.total / pageSize);
  return (
    <nav className="catalog-pagination" aria-label="Catalog 상품 페이지">
      <small>{page.total === 0 ? "0건" : `${page.offset + 1}–${page.offset + page.items.length} / 총 ${page.total}건`}</small>
      <div className="catalog-page-buttons">
        <button type="button" aria-label="이전 페이지" disabled={currentPage <= 1} onClick={() => onPageChange(currentPage - 1)}>‹</button>
        {catalogPageNumbers(currentPage, totalPages).map((item, index) => item === "ellipsis" ? (
          <span key={`ellipsis-${index}`} aria-hidden="true">…</span>
        ) : (
          <button key={item} type="button" aria-label={`${item} 페이지`}
            aria-current={currentPage === item ? "page" : undefined}
            className={currentPage === item ? "active" : undefined}
            onClick={() => onPageChange(item)}>{item}</button>
        ))}
        <button type="button" aria-label="다음 페이지" disabled={totalPages === 0 || currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}>›</button>
      </div>
    </nav>
  );
}

export default function CatalogBrowser() {
  const [urlState, setUrlState] = useState(() => readCatalogUrl(window.location.search));
  const [searchDraft, setSearchDraft] = useState(urlState.q);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [priceOpen, setPriceOpen] = useState(false);
  const [priceMinDraft, setPriceMinDraft] = useState(urlState.price_min?.toString() ?? "");
  const [priceMaxDraft, setPriceMaxDraft] = useState(urlState.price_max?.toString() ?? "");
  const [priceError, setPriceError] = useState("");
  const priceRef = useRef<HTMLDivElement>(null);
  const [summary, setSummary] = useState<CatalogSummary | null>(null);
  const [summaryError, setSummaryError] = useState(false);
  const [productsPage, setProductsPage] = useState<CatalogProductsPage | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState(false);
  const [roots, setRoots] = useState<CatalogHierarchyCategory[] | null>(null);
  const [middles, setMiddles] = useState<CatalogHierarchyCategory[] | null>(null);
  const [leaves, setLeaves] = useState<CatalogHierarchyCategory[] | null>(null);
  const [middleParentId, setMiddleParentId] = useState<string | null>(null);
  const [leafParentId, setLeafParentId] = useState<string | null>(null);
  const [hierarchyError, setHierarchyError] = useState(false);
  const aiDrawer = useOptionalCommonAiDrawer();
  function changeUrl(patch: Partial<CatalogUrlState>, mode: "push" | "replace" = "push") {
    const next = { ...readCatalogUrl(window.location.search), ...patch };
    writeCatalogUrl(next, mode);
    setUrlState(next);
    if (patch.q !== undefined) setSearchDraft(next.q);
  }

  useEffect(() => {
    const readHistory = () => {
      const next = readCatalogUrl(window.location.search);
      setUrlState(next);
      setSearchDraft(next.q);
      setPriceMinDraft(next.price_min?.toString() ?? "");
      setPriceMaxDraft(next.price_max?.toString() ?? "");
      setPriceError("");
      setPriceOpen(false);
    };
    window.addEventListener("popstate", readHistory);
    const rawPage = new URLSearchParams(window.location.search).get("page");
    if (rawPage !== null && rawPage !== String(readCatalogUrl(window.location.search).page)) {
      writeCatalogUrl(readCatalogUrl(window.location.search), "replace");
    }
    return () => window.removeEventListener("popstate", readHistory);
  }, []);

  useEffect(() => {
    if (!priceOpen) return;
    const closeOnOutside = (event: PointerEvent) => {
      if (!priceRef.current?.contains(event.target as Node)) setPriceOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPriceOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [priceOpen]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    getCatalogSummary(controller.signal)
      .then((response) => { if (active) setSummary(response.data); })
      .catch(() => { if (active) setSummaryError(true); });
    return () => { active = false; controller.abort(); };
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    getCatalogCategories(1, undefined, controller.signal)
      .then((response) => { if (active) setRoots(response.data); })
      .catch(() => { if (active) setHierarchyError(true); });
    return () => { active = false; controller.abort(); };
  }, []);

  const selectedRoot = roots?.find((item) => item.cafe24_category_no === urlState.category_1);
  const selectedMiddle = middleParentId === selectedRoot?.id
    ? middles?.find((item) => item.cafe24_category_no === urlState.category_2) : undefined;
  const selectedLeaf = leafParentId === selectedMiddle?.id
    ? leaves?.find((item) => item.cafe24_category_no === urlState.category_3) : undefined;

  useEffect(() => {
    if (roots !== null && urlState.category_1 !== null && !selectedRoot) {
      changeUrl({ category_1: null, category_2: null, category_3: null, page: 1 }, "replace");
    }
  }, [roots, urlState.category_1, selectedRoot]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setMiddleParentId(selectedRoot?.id ?? null);
    setMiddles(selectedRoot ? null : []);
    if (selectedRoot) {
      getCatalogCategories(2, selectedRoot.id, controller.signal)
        .then((response) => { if (active) setMiddles(response.data); })
        .catch(() => { if (active) setHierarchyError(true); });
    }
    return () => { active = false; controller.abort(); };
  }, [selectedRoot?.id]);

  useEffect(() => {
    if (middles !== null && middleParentId === selectedRoot?.id &&
      urlState.category_2 !== null && !selectedMiddle) {
      changeUrl({ category_2: null, category_3: null, page: 1 }, "replace");
    }
  }, [middles, middleParentId, selectedRoot?.id, urlState.category_2, selectedMiddle]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLeafParentId(selectedMiddle?.id ?? null);
    setLeaves(selectedMiddle ? null : []);
    if (selectedMiddle) {
      getCatalogCategories(3, selectedMiddle.id, controller.signal)
        .then((response) => { if (active) setLeaves(response.data); })
        .catch(() => { if (active) setHierarchyError(true); });
    }
    return () => { active = false; controller.abort(); };
  }, [selectedMiddle?.id]);

  useEffect(() => {
    if (leaves !== null && leafParentId === selectedMiddle?.id &&
      urlState.category_3 !== null && !selectedLeaf) {
      changeUrl({ category_3: null, page: 1 }, "replace");
    }
  }, [leaves, leafParentId, selectedMiddle?.id, urlState.category_3, selectedLeaf]);

  const hierarchyReady = (roots !== null || (hierarchyError && urlState.category_1 === null)) &&
    (urlState.category_1 === null || !!selectedRoot) &&
    (urlState.category_2 === null || !!selectedMiddle) &&
    (urlState.category_3 === null || !!selectedLeaf);
  const categoryNo = selectedLeaf?.cafe24_category_no ?? selectedMiddle?.cafe24_category_no ??
    selectedRoot?.cafe24_category_no;
  const viewSearch = urlState.q.trim();
  const safeViewSearch = viewSearch.length <= 80 &&
    /^[A-Za-z0-9가-힣 &()_.-]*$/.test(viewSearch) &&
    !/(?:order[_ -]?id|order[_ -]?item[_ -]?id|order[_ -]?line[_ -]?id|customer[_ -]?id|inquiry|payment|shipping|고객\s*(?:이름|성명|전화|주소|메일)|문의\s*원문)/i.test(viewSearch) &&
    !/(?:^|[^\d])01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?:$|[^\d])/.test(viewSearch) &&
    !/\b\d{8}-\d{6,}\b/.test(viewSearch);

  useEffect(() => {
    if (!hierarchyReady) return;
    let active = true;
    const controller = new AbortController();
    setPageLoading(true);
    setPageError(false);
    const query: CatalogProductsQuery = {
      sort_by: urlState.sort_by,
      sort_dir: urlState.sort_dir,
    };
    if (urlState.q.trim()) query.q = urlState.q.trim();
    if (urlState.display_status) query.display_status = urlState.display_status;
    if (urlState.selling_status) query.selling_status = urlState.selling_status;
    if (urlState.sold_out) query.sold_out = urlState.sold_out === "true";
    if (urlState.price_min !== null) query.price_min = urlState.price_min;
    if (urlState.price_max !== null) query.price_max = urlState.price_max;
    if (categoryNo !== undefined) query.category_no = categoryNo;
    getCatalogProducts(pageSize, (urlState.page - 1) * pageSize, controller.signal, query)
      .then((response) => {
        if (!active) return;
        const maxPage = Math.max(1, Math.ceil(response.data.total / pageSize));
        if (urlState.page > maxPage) {
          changeUrl({ page: maxPage }, "replace");
          return;
        }
        setProductsPage(response.data);
        setPageLoading(false);
      })
      .catch(() => { if (active) { setPageError(true); setPageLoading(false); } });
    return () => { active = false; controller.abort(); };
  }, [hierarchyReady, categoryNo, urlState.page, urlState.q, urlState.display_status,
    urlState.selling_status, urlState.sold_out, urlState.price_min, urlState.price_max,
    urlState.sort_by, urlState.sort_dir]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    changeUrl({ q: searchDraft.trim(), page: 1 });
  }

  function changeSort(sortBy: CatalogSortBy) {
    changeUrl({ sort_by: sortBy,
      sort_dir: urlState.sort_by === sortBy && urlState.sort_dir === "desc" ? "asc" : "desc",
      page: 1 });
  }

  function applyPrice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const minText = priceMinDraft.trim();
    const maxText = priceMaxDraft.trim();
    const validNumber = (value: string) => value === "" || /^\d+(?:\.\d+)?$/.test(value) && Number.isFinite(Number(value));
    if (!validNumber(minText) || !validNumber(maxText)) {
      setPriceError("가격은 0 이상의 숫자로 입력해 주세요.");
      return;
    }
    const min = minText === "" ? null : Number(minText);
    const max = maxText === "" ? null : Number(maxText);
    if (min !== null && max !== null && min > max) {
      setPriceError("최소 가격은 최대 가격보다 클 수 없습니다.");
      return;
    }
    setPriceError("");
    setPriceOpen(false);
    changeUrl({ price_min: min, price_max: max, page: 1 });
  }

  function clearPrice() {
    setPriceMinDraft("");
    setPriceMaxDraft("");
    setPriceError("");
    setPriceOpen(false);
    changeUrl({ price_min: null, price_max: null, page: 1 });
  }

  const sortArrow = (sortBy: CatalogSortBy) => urlState.sort_by === sortBy
    ? (urlState.sort_dir === "desc" ? " ↓" : " ↑") : " ↕";

  return (
    <section aria-labelledby="catalog-section-title" data-testid="catalog-section" className="catalog-section">
    <h2 id="catalog-section-title" className="common-ai-sr-only">
      상품 목록
    </h2>

    {summaryError ? (
      <SystemState
        state="denied"
        title="상품 정보를 불러오지 못했습니다"
      />
    ) : !summary ? (
      <SystemState state="loading" />
    ) : (
      <div className="catalog-summary-inline">
        <span>상품 {summary.product_count}건</span>
        <span>카테고리 {summary.category_count}건</span>
        <span>상품·카테고리 관계 {summary.product_category_count}건</span>
        <span className="catalog-summary-source">
          원본 기준시각{" "}
          {summary.source_as_of === null ? (
            "미확인"
          ) : (
            <time dateTime={summary.source_as_of}>
              {new Date(summary.source_as_of).toLocaleString("ko-KR")}
            </time>
          )}
        </span>
      </div>
    )}
      <div className="catalog-toolbar catalog-toolbar-compact">
        <div className="catalog-primary-controls">
          <form onSubmit={submitSearch} className="catalog-search">
            <input aria-label="Catalog 검색어" placeholder="상품 번호 · 코드 · 판매가 · 카테고리 검색"
              value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} />
          </form>
          <button
            type="button"
            className="catalog-filter-toggle"
            aria-expanded={filtersOpen}
            aria-controls="catalog-advanced-filters"
            onClick={() => {
              setFiltersOpen((value) => !value);
              setPriceOpen(false);
            }}
          >
            필터
            <span aria-hidden="true">
              {filtersOpen ? "⌃" : "⌄"}
            </span>
          </button>
            </div>

            <div
              id="catalog-advanced-filters"
              className="catalog-controls catalog-advanced-filters"
              hidden={!filtersOpen}
            >
          <div className="catalog-price-inline">
            <form
              className="catalog-price-inline-form"
              onSubmit={applyPrice}
              role="group"
              aria-label="판매가 범위"
            >
              <label>
                최소 가격
                <input
                  type="text"
                  inputMode="decimal"
                  value={priceMinDraft}
                  aria-invalid={!!priceError}
                  placeholder="0"
                  onChange={(event) => {
                    setPriceMinDraft(event.target.value);
                    setPriceError("");
                  }}
                />
              </label>

              <label>
                최대 가격
                <input
                  type="text"
                  inputMode="decimal"
                  value={priceMaxDraft}
                  aria-invalid={!!priceError}
                  placeholder="제한 없음"
                  onChange={(event) => {
                    setPriceMaxDraft(event.target.value);
                    setPriceError("");
                  }}
                />
              </label>

              <div className="catalog-price-actions">
                <button type="button" onClick={clearPrice}>
                  초기화
                </button>
                <button type="submit">적용</button>
              </div>

              {priceError && <p role="alert">{priceError}</p>}
            </form>
          </div>
          <select aria-label="진열 필터" value={urlState.display_status}
            onChange={(event) => changeUrl({ display_status: event.target.value as CatalogUrlState["display_status"], page: 1 })}>
            <option value="">진열 전체</option><option value="T">진열</option><option value="F">미진열</option>
          </select>
          <select aria-label="판매 필터" value={urlState.selling_status}
            onChange={(event) => changeUrl({ selling_status: event.target.value as CatalogUrlState["selling_status"], page: 1 })}>
            <option value="">판매 전체</option><option value="T">판매중</option><option value="F">판매중지</option>
          </select>
          <select aria-label="품절 필터" value={urlState.sold_out}
            onChange={(event) => changeUrl({ sold_out: event.target.value as CatalogUrlState["sold_out"], page: 1 })}>
            <option value="">품절 전체</option><option value="true">품절</option><option value="false">품절 아님</option>
          </select>
          <select aria-label="대주제" value={urlState.category_1 ?? ""} disabled={roots === null}
            onChange={(event) => changeUrl({ category_1: event.target.value === "" ? null : Number(event.target.value),
              category_2: null, category_3: null, page: 1 })}>
            <option value="">대주제 전체</option>
            {roots?.map((item) => <option key={item.id} value={item.cafe24_category_no}>{item.category_name}</option>)}
          </select>
          <select aria-label="중간주제" value={urlState.category_2 ?? ""}
            disabled={!selectedRoot || middleParentId !== selectedRoot.id || middles === null || middles.length === 0}
            onChange={(event) => changeUrl({ category_2: event.target.value === "" ? null : Number(event.target.value),
              category_3: null, page: 1 })}>
            <option value="">중간주제 전체</option>
            {middles?.map((item) => <option key={item.id} value={item.cafe24_category_no}>{item.category_name}</option>)}
          </select>
          <select aria-label="소주제" value={urlState.category_3 ?? ""}
            disabled={!selectedMiddle || leafParentId !== selectedMiddle.id || leaves === null || leaves.length === 0}
            onChange={(event) => changeUrl({ category_3: event.target.value === "" ? null : Number(event.target.value), page: 1 })}>
            <option value="">소주제 전체</option>
            {leaves?.map((item) => <option key={item.id} value={item.cafe24_category_no}>{item.category_name}</option>)}
          </select>
        </div>
      </div>
      {hierarchyError && <p role="alert">카테고리 목록을 불러오지 못했습니다.</p>}
      {pageError && <SystemState state="denied" title="상품 페이지를 불러오지 못했습니다" />}
      {pageLoading && <p role="status">상품 페이지 {urlState.page} 불러오는 중입니다.</p>}
      {!productsPage && !pageError ? <SystemState state="loading" /> :
        productsPage?.items.length === 0 ? <SystemState state="empty" title="표시할 Catalog 상품이 없습니다" /> :
          productsPage ? (
            <div className="card catalog-table-wrap">
              <table className="dense-table">
                <thead><tr>
                  <th aria-sort={urlState.sort_by === "cafe24_product_no" ?
                    urlState.sort_dir === "desc" ? "descending" : "ascending" : "none"}>
                    <button
                      type="button"
                      className="catalog-sort"
                      onClick={() => changeSort("cafe24_product_no")}
                    >
                      상품 번호{sortArrow("cafe24_product_no")}
                    </button>
                  </th>
                  {aiDrawer && <th className="catalog-ai-column">운영 AI</th>}
                  <th>상품명</th><th>상품 코드</th><th>사용자 상품 코드</th>
                  <th aria-sort={urlState.sort_by === "sale_price" ?
                    urlState.sort_dir === "desc" ? "descending" : "ascending" : "none"}>
                    <button type="button" className="catalog-sort" onClick={() => changeSort("sale_price")}>판매가{sortArrow("sale_price")}</button>
                  </th>
                  <th>진열 상태</th><th>판매 상태</th><th>품절</th><th>카테고리</th>
                </tr></thead>
                <tbody>{productsPage.items.map((product) => <tr key={product.id}>
                  <td>{product.cafe24_product_no}</td>
                  {aiDrawer && (
                    <td className="catalog-ai-column">
                      <button
                        type="button"
                        onClick={() =>
                          aiDrawer.openAiDrawer({
                            targetType: "PRODUCT",
                            targetId: String(product.cafe24_product_no),
                            targetLabel: product.product_name,
                            source: "CAFE24_CATALOG",
                            asOf: product.source_as_of,
                          })
                        }
                        aria-label={`${product.product_name} 운영 AI 열기`}
                      >
                        운영 AI
                      </button>
                    </td>
                  )}
                  <td>{product.product_name}</td>
                  <td>{product.product_code}</td><td>{product.custom_product_code ?? "미확인"}</td>
                  <td>{product.sale_price === null ? "미확인" : product.sale_price.toLocaleString("ko-KR")}</td>
                  <td>{product.display_status === "T" ? "진열" : "미진열"}</td>
                  <td>{product.selling_status === "T" ? "판매중" : "판매중지"}</td>
                  <td>{product.sold_out ? "품절" : "품절 아님"}</td>
                  <td>{product.categories.length ? product.categories.map((item) => item.category_name).join(" · ") : "미확인"}</td>
                </tr>)}</tbody>
              </table>
            </div>
          ) : null}
      {productsPage && <CatalogPagination page={productsPage} currentPage={urlState.page}
        onPageChange={(page) => changeUrl({ page })} />}
    </section>
  );
}

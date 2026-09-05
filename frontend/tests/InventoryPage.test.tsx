import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import InventoryPage from "../src/app/pages/InventoryPage";
import { mockHandlers } from "../src/mocks/handlers";

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("InventoryPage", () => {
  it("재고 Snapshot 계약 데이터를 표시한다", async () => {
    render(<InventoryPage />);

    expect(
      screen.getByTestId("route-inventory"),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getAllByText("sku_demo_001").length,
      ).toBe(2);
    });

    expect(
      screen.getByText("sku_demo_002"),
    ).toBeInTheDocument();

    expect(
      screen.getAllByText("계약 미제공").length,
    ).toBeGreaterThan(0);
  });

  it("STALE 재고가 있으면 경고를 표시한다", async () => {
    render(<InventoryPage />);

    expect(
      await screen.findByTestId(
        "inventory-stale-warning",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "오래된 재고 데이터 1건이 있습니다.",
      ),
    ).toBeInTheDocument();
  });

  it("Production write CTA를 표시하지 않는다", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<InventoryPage />);

    await screen.findByText("sku_demo_002");

    const prohibitedCtas = [
      /재고 수정/i,
      /재고 동기화/i,
      /수량 변경/i,
      /가격 변경/i,
      /주문 취소/i,
      /환불/i,
    ];

    for (const name of prohibitedCtas) {
      expect(
        screen.queryByRole("button", { name }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name }),
      ).not.toBeInTheDocument();
    }

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("STALE 재고를 최신 재고보다 먼저 표시한다", async () => {
    const { container } = render(<InventoryPage />);

    await screen.findByText("sku_demo_002");

    const rows = Array.from(
      container.querySelectorAll("tbody tr"),
    );

    expect(rows).toHaveLength(3);

    expect(rows[0].textContent).toContain(
      "sku_demo_001",
    );

    expect(rows[0].textContent).toContain(
      "ECOUNT",
    );
  });

  it("재고 데이터가 비어 있으면 Empty 상태를 표시한다", async () => {
    const handler = mockHandlers.find(
      (candidate) =>
        candidate.method === "GET" &&
        candidate.path === "/api/v1/inventory",
    );

    expect(handler).toBeDefined();

    if (!handler) {
      return;
    }

    vi.spyOn(handler, "resolve").mockReturnValue({
      schema_version: "1.0",
      tenant_id: "demo_store",
      request_id: "req_inventory_empty",
      trace_id: "tr_inventory_empty",
      data: [],
      evidence_ids: [],
      warnings: [],
      as_of: "2026-09-02T06:30:00Z",
    });

    render(<InventoryPage />);

    expect(
      await screen.findByText(
        "표시할 재고가 없습니다",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "현재 조회 가능한 재고 Snapshot이 없습니다.",
      ),
    ).toBeInTheDocument();
  });

  it("CARD_GAME 필터는 해당 SKU만 표시한다", async () => {
    render(<InventoryPage />);

    await screen.findByText("sku_demo_002");

    fireEvent.change(
        screen.getByLabelText("카테고리 필터"),
        {
        target: { value: "CARD_GAME" },
        },
    );

    expect(
        screen.getByText("sku_demo_002"),
    ).toBeInTheDocument();

    expect(
        screen.queryByText("sku_demo_001"),
    ).not.toBeInTheDocument();
    });

    it("STRATEGY 필터는 같은 SKU의 채널별 Snapshot 두 행을 유지한다", async () => {
    render(<InventoryPage />);

    await screen.findByText("sku_demo_002");

    fireEvent.change(
        screen.getByLabelText("카테고리 필터"),
        {
        target: { value: "STRATEGY" },
        },
    );

    expect(
        screen.getAllByText("sku_demo_001"),
    ).toHaveLength(2);

    expect(
        screen.queryByText("sku_demo_002"),
    ).not.toBeInTheDocument();
    });

    it("계약에 없는 필터는 비활성 상태로 표시한다", async () => {
    render(<InventoryPage />);

    await screen.findByText("sku_demo_002");

    expect(
        screen.getByLabelText("언어 필터"),
    ).toBeDisabled();

    expect(
        screen.getByLabelText("관계 필터"),
    ).toBeDisabled();

    expect(
        screen.getByLabelText("위험 필터"),
    ).toBeDisabled();

    expect(
      screen.getByText(
        "언어·관계·위험 필터는 현재 계약에서 제공되지 않습니다.",
      ),
    ).toBeInTheDocument();
    });

    it("brand와 category 복합 필터 결과가 Fixture와 일치한다", async () => {
    render(<InventoryPage />);

    await screen.findByText("sku_demo_002");

    fireEvent.change(
      screen.getByLabelText("브랜드 필터"),
      {
        target: { value: "brand_demo_001" },
      },
    );
    fireEvent.change(
      screen.getByLabelText("카테고리 필터"),
      {
        target: { value: "CARD_GAME" },
      },
    );

    expect(
      screen.getByRole("row", {
        name: /sku_demo_002 TOSS_POS 재고 상세 열기/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("sku_demo_001"),
    ).not.toBeInTheDocument();
    });

    it("Enter와 Space로 상세 패널을 열고 닫는다", async () => {
    render(<InventoryPage />);

    const row = await screen.findByRole("row", {
      name: /sku_demo_001 ECOUNT 재고 상세 열기/i,
    });

    fireEvent.keyDown(row, {
      key: "Enter",
    });

    expect(
      screen.getByRole("dialog", {
        name: "sku_demo_001",
      }),
    ).toBeInTheDocument();
    expect(row).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(row).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    fireEvent.keyDown(row, {
      key: " ",
    });

    expect(
      screen.queryByTestId("inventory-detail-panel"),
    ).not.toBeInTheDocument();
    expect(row).toHaveFocus();
    });

    it("재고 행을 선택하면 해당 Snapshot 상세 패널을 연다", async () => {
    render(<InventoryPage />);

    const row = await screen.findByRole("row", {
        name: /sku_demo_001 ECOUNT 재고 상세 열기/i,
    });

    fireEvent.click(row);

    const panel = screen.getByTestId(
        "inventory-detail-panel",
    );

    expect(panel).toBeInTheDocument();
    expect(panel).toHaveAttribute("role", "dialog");
    expect(panel).toHaveAttribute("aria-modal", "true");
    expect(panel).toHaveAccessibleName("sku_demo_001");

    expect(
    within(panel).getByRole("heading", {
        name: "sku_demo_001",
    }),
    ).toBeInTheDocument();

    expect(
      within(panel).getAllByText("ECOUNT"),
    ).toHaveLength(1);

    expect(
        within(panel).getByText("3"),
    ).toBeInTheDocument();

    expect(
        within(panel).getByText("4"),
    ).toBeInTheDocument();
    });

    it("같은 재고 행을 다시 선택하면 상세 패널을 닫는다", async () => {
    render(<InventoryPage />);

    const row = await screen.findByRole("row", {
        name: /sku_demo_001 ECOUNT 재고 상세 열기/i,
    });

    fireEvent.click(row);

    expect(
        screen.getByTestId("inventory-detail-panel"),
    ).toBeInTheDocument();

    fireEvent.click(row);

    expect(
        screen.queryByTestId("inventory-detail-panel"),
    ).not.toBeInTheDocument();
    });

    it("다른 재고 행을 선택하면 열린 상세 패널의 Snapshot을 교체한다", async () => {
    render(<InventoryPage />);

    const ecountRow = await screen.findByRole("row", {
        name: /sku_demo_001 ECOUNT 재고 상세 열기/i,
    });

    const cafe24Row = screen.getByRole("row", {
        name: /sku_demo_001 CAFE24 재고 상세 열기/i,
    });

    fireEvent.click(ecountRow);

    let panel = screen.getByTestId(
        "inventory-detail-panel",
    );

    expect(
      within(panel).getAllByText("ECOUNT"),
    ).toHaveLength(1);

    fireEvent.click(cafe24Row);

    panel = screen.getByTestId(
        "inventory-detail-panel",
    );

    expect(
      within(panel).getAllByText("CAFE24"),
    ).toHaveLength(1);

    expect(
        within(panel).queryByText("ECOUNT"),
    ).not.toBeInTheDocument();
    });

    it("Escape로 상세 패널을 닫고 원래 재고 행으로 focus를 복귀한다", async () => {
    render(<InventoryPage />);

    const row = await screen.findByRole("row", {
        name: /sku_demo_001 ECOUNT 재고 상세 열기/i,
    });

    fireEvent.click(row);

    const closeButton = screen.getByRole(
        "button",
        {
        name: "재고 상세 닫기",
        },
    );

    await waitFor(() => {
        expect(closeButton).toHaveFocus();
    });

    fireEvent.keyDown(window, {
        key: "Escape",
    });

    await waitFor(() => {
        expect(
        screen.queryByTestId(
            "inventory-detail-panel",
        ),
        ).not.toBeInTheDocument();

        expect(row).toHaveFocus();
    });
    });

    it("재고 검토 Task는 제안 후보로 표시하고 SKU 직접 연결을 확정하지 않는다", async () => {
    render(<InventoryPage />);

    const row = await screen.findByRole("row", {
        name: /sku_demo_001 ECOUNT 재고 상세 열기/i,
    });

    fireEvent.click(row);

    const panel = screen.getByTestId(
        "inventory-detail-panel",
    );

    expect(
        within(panel).getByText(
        "합성 SKU 재고 차이 확인",
        ),
    ).toBeInTheDocument();

    expect(
        within(panel).getByText(
        /우선순위:\s*HIGH/,
        ),
    ).toBeInTheDocument();

    expect(
        within(panel).getByText(
        /상태:\s*PROPOSED/,
        ),
    ).toBeInTheDocument();

    expect(
        within(panel).getByText(
        /제안 이유:\s*inventory discrepancy/,
        ),
    ).toBeInTheDocument();

    expect(
        within(panel).getByText(
        /SKU 직접 연결 정보가 없어/,
        ),
    ).toBeInTheDocument();
    });
});

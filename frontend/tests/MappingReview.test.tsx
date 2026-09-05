import {
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MappingReview from "../src/features/inventory/MappingReview";
import { mappingReviewItems } from "../src/mocks/fixtures";

describe("MappingReview", () => {
  it("Frontend Demo View Model 경계를 명시한다", () => {
    render(
      <MappingReview
        items={mappingReviewItems}
        environment="DEMO"
      />,
    );

    expect(
      screen.getByText(/실제 Backend Mapping Projection이 아닙니다/),
    ).toBeInTheDocument();
  });

  it("후보가 여러 개여도 자동 선택하지 않는다", () => {
    render(
      <MappingReview
        items={mappingReviewItems}
        environment="DEMO"
      />,
    );

    const firstItem = screen
      .getByText("Synthetic Game Korean Edition")
      .closest("article");

    expect(firstItem).not.toBeNull();

    expect(
      within(firstItem!).getByRole("button", {
        name: /sku_demo_001/i,
      }),
    ).toHaveAttribute("aria-pressed", "false");

    expect(
      within(firstItem!).getByRole("button", {
        name: /sku_demo_002/i,
      }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("후보가 하나여도 자동 선택하지 않는다", () => {
    render(
      <MappingReview
        items={mappingReviewItems}
        environment="DEMO"
      />,
    );

    const item = screen
      .getByText("Synthetic Card Game Standard")
      .closest("article");

    expect(item).not.toBeNull();

    expect(
      within(item!).getByRole("button", {
        name: /sku_demo_002/i,
      }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("후보를 선택하고 다시 누르면 선택을 해제한다", () => {
    render(
      <MappingReview
        items={mappingReviewItems}
        environment="DEMO"
      />,
    );

    const item = screen
      .getByText("Synthetic Game Korean Edition")
      .closest("article");

    const candidate = within(item!).getByRole(
      "button",
      {
        name: /sku_demo_001/i,
      },
    );

    fireEvent.click(candidate);

    expect(candidate).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(candidate);

    expect(candidate).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("Demo에서는 선택한 후보의 검토 결정을 저장한다", () => {
    render(
      <MappingReview
        items={mappingReviewItems}
        environment="DEMO"
      />,
    );

    const item = screen
      .getByText("Synthetic Game Korean Edition")
      .closest("article");

    fireEvent.click(
      within(item!).getByRole("button", {
        name: /sku_demo_001/i,
      }),
    );

    fireEvent.click(
      within(item!).getByRole("button", {
        name: "Demo 검토 결정 저장",
      }),
    );

    expect(
      within(item!).getByText(
        /Demo 검토 결정이 저장되었습니다/,
      ),
    ).toBeInTheDocument();
  });

  it("Production Read-Only에서는 검토 결정을 저장할 수 없다", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    render(
      <MappingReview
        items={mappingReviewItems}
        environment="PRODUCTION_READ"
      />,
    );

    const item = screen
      .getByText("Synthetic Game Korean Edition")
      .closest("article");

    fireEvent.click(
      within(item!).getByRole("button", {
        name: /sku_demo_001/i,
      }),
    );

    expect(
      within(item!).getByRole("button", {
        name: "Demo 검토 결정 저장",
      }),
    ).toBeDisabled();

    expect(
      within(item!).getByText(
        /Production Read-Only에서는 저장할 수 없으며/,
      ),
    ).toBeInTheDocument();

    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("후보 그룹과 저장 제한 설명을 접근 가능한 이름으로 연결한다", () => {
    render(
      <MappingReview
        items={mappingReviewItems}
        environment="DEMO"
      />,
    );

    const item = screen
      .getByText("Synthetic Game Korean Edition")
      .closest("article");

    expect(
      within(item!).getByRole("group", {
        name: "Synthetic Game Korean Edition SKU 후보",
      }),
    ).toBeInTheDocument();

    expect(
      within(item!).getByRole("button", {
        name: "Demo 검토 결정 저장",
      }),
    ).toHaveAccessibleDescription(
      /후보를 선택해야 저장할 수 있습니다/,
    );
  });

  it("후보가 없으면 미연결 상태로 유지한다", () => {
    render(
        <MappingReview
        items={mappingReviewItems}
        environment="DEMO"
        />,
    );

    const item = screen
        .getByText("Unknown Synthetic Product")
        .closest("article");

    expect(item).not.toBeNull();

    expect(
        within(item!).getByText(
        /연결 가능한 SKU 후보가 없습니다/,
        ),
    ).toBeInTheDocument();

    expect(
        within(item!).queryByRole("button", {
        name: /sku_demo_/i,
        }),
    ).not.toBeInTheDocument();
    });
});

import {
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import {
  describe,
  expect,
  it,
} from "vitest";

import CitationCard from "../src/features/inquiries/CitationCard";

const citation = {
  source_type: "product",
  source_id: "prd_demo_001",
  title: "Synthetic Expansion Product",
  record_or_field: "compatibility",
  as_of: "2026-09-07T06:00:00Z",
  score: 0.92,
};

describe("CitationCard", () => {
  it("핵심 citation 정보를 표시한다", () => {
    render(
      <CitationCard
        citation={citation}
        defaultOpen
      />,
    );

    expect(
      screen.getByText(
        "Synthetic Expansion Product",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText("prd_demo_001"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("compatibility"),
    ).toBeInTheDocument();

    expect(
    screen.getAllByText("92%"),
    ).toHaveLength(2);
  });

  it("as_of를 time element로 표시한다", () => {
    const { container } = render(
      <CitationCard
        citation={citation}
        defaultOpen
      />,
    );

    const time = container.querySelector("time");

    expect(time).toHaveAttribute(
      "datetime",
      "2026-09-07T06:00:00Z",
    );
  });

  it("summary로 citation 상세를 열고 닫을 수 있다", () => {
    render(
      <CitationCard citation={citation} />,
    );

    const summary = screen.getByText(
      "Synthetic Expansion Product",
    );

    expect(summary.closest("details")).not.toHaveAttribute(
      "open",
    );

    fireEvent.click(summary);

    expect(summary.closest("details")).toHaveAttribute(
      "open",
    );
  });

  it("긴 필드와 미지 source_type, 오래된 as_of를 제공된 값 그대로 표시한다", () => {
    const edgeCitation = {
      source_type: "future_connector_record",
      source_id:
        "synthetic-source-id-with-a-very-long-unbroken-segment-001",
      title:
        "합성 데이터로 만든 매우 긴 Citation 제목이며 좁은 화면에서도 원문을 생략하거나 다른 출처를 만들지 않습니다",
      record_or_field:
        "synthetic.deeply_nested_record_or_field_with_a_long_unbroken_segment",
      as_of: "2020-01-01T00:00:00Z",
      score: 0.51,
    };

    render(
      <CitationCard
        citation={edgeCitation}
        defaultOpen
      />,
    );

    expect(
      screen.getByText(new RegExp(edgeCitation.source_type)),
    ).toBeInTheDocument();
    expect(
      screen.getByText(edgeCitation.source_id),
    ).toBeInTheDocument();
    expect(
      screen.getByText(edgeCitation.title),
    ).toBeInTheDocument();
    expect(
      screen.getByText(edgeCitation.record_or_field),
    ).toBeInTheDocument();
    expect(
      screen.getByText(edgeCitation.as_of),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/stale|오래됨/i),
    ).not.toBeInTheDocument();
  });
});
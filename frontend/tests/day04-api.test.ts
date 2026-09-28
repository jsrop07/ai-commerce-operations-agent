import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiEnvelope } from "../src/types/contracts";
import { getC04Lookup, toUrgentQueueItems } from "../src/api/day04";

function envelope(data: unknown[], requestId = "req_day04"): ApiEnvelope<unknown[]> {
  return {
    schema_version: "1.0",
    tenant_id: "demo_store",
    request_id: requestId,
    trace_id: "tr_day04",
    data,
    evidence_ids: [],
    warnings: [],
    as_of: "2026-09-03T04:40:00Z",
  };
}

describe("Day 4 insight API boundary", () => {
  const insight = { insight_id: "ins_c04", type: "INVENTORY_RISK", severity: "LOW", confidence: 1, summary: "요약" };
  const key = { source_id: "backend_source", version: "v3", chunk_id: "backend_source:v3:c04:0" };

  it("Backend C04 key의 세 필드를 변환 없이 보존한다", () => {
    expect(toUrgentQueueItems(envelope([{ ...insight, c04_lookup: key }]))[0].data.c04_lookup).toEqual(key);
  });

  it.each([undefined, null])("C04 key 누락은 다른 ID로 채우지 않는다 (%s)", (c04_lookup) => {
    expect(toUrgentQueueItems(envelope([{ ...insight, c04_lookup,
      evidence_ids: ["not-a-key"], sku_id: "not-a-source", reservation_id: "reservation", order_id: "order",
    }]))[0].data.c04_lookup).toBeUndefined();
  });

  it.each([
    {}, "source", { ...key, source_id: "" }, { ...key, source_id: 123 },
    { ...key, source_id: "bad/source" }, { ...key, version: " " },
    { ...key, version: "v".repeat(129) }, { ...key, chunk_id: undefined },
    { ...key, chunk_id: 3 }, { ...key, chunk_id: " " }, { ...key, chunk_id: "x".repeat(301) },
  ])("malformed C04 key를 fail closed 처리한다", (c04_lookup) => {
    expect(() => toUrgentQueueItems(envelope([{ ...insight, c04_lookup }]))).toThrow("Backend C04 lookup key is malformed");
  });
  it("Queue에 필요한 공통 필드만 소비하고 evidence/proposal을 만들지 않는다", () => {
    const [item] = toUrgentQueueItems(
      envelope([
        {
          insight_id: "ins_day04",
          type: "INVENTORY_RISK",
          severity: "LOW",
          confidence: 1,
          summary: "오프라인 판매가 예상 재고에 반영되었습니다.",
          evidence_ids: ["evt_day04"],
          correlation_id: "corr_day04",
          calculation: { expected_inventory: 6 },
          model_run_id: null,
          rule_version: "shadow-inventory-v1",
        },
      ]),
    );

    expect(item.data).toEqual({
      insight_id: "ins_day04",
      type: "INVENTORY_RISK",
      severity: "LOW",
      confidence: 1,
      summary: "오프라인 판매가 예상 재고에 반영되었습니다.",
    });
    expect(item.data).not.toHaveProperty("evidence");
    expect(item.data).not.toHaveProperty("proposal");
  });

  it("빈 insight 목록을 빈 Queue로 유지한다", () => {
    expect(toUrgentQueueItems(envelope([]))).toEqual([]);
  });

  it("malformed insight item은 화면 계약으로 단언하지 않고 거부한다", () => {
    expect(() =>
      toUrgentQueueItems(envelope([{ insight_id: "missing-fields" }]))
    ).toThrow("Backend insight item is malformed");
  });

  it("긴 request_id를 자르거나 바꾸지 않는다", () => {
    const requestId = `req_${"x".repeat(512)}`;
    const [item] = toUrgentQueueItems(
      envelope(
        [{
          insight_id: "ins_day04",
          type: "INVENTORY_RISK",
          severity: "LOW",
          confidence: 1,
          summary: "요약",
        }],
        requestId,
      ),
    );

    expect(item.request_id).toBe(requestId);
  });
});

describe("C04 lookup API boundary (synthetic)", () => {
  afterEach(() => vi.unstubAllGlobals());
  const key = { source_id: "product_demo_001", version: "v1", chunk_id: "product_demo_001:v1:c04:0" };
  const document = {
    ...key, title: "Synthetic board game", source_type: "PRODUCT",
    as_of: "2026-09-26T00:00:00Z", excerpt: "합성 보드게임: 2–4명, 한국어판.",
    excerpt_hash: "sha256:test", stale: false, warnings: [],
    data_mode: "SYNTHETIC_DEMO", visibility: "DEMO_PUBLIC", definitive_answer_allowed: false,
  };

  it("전달된 key와 abort signal만 사용한다", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...envelope([]), data: document })));
    vi.stubGlobal("fetch", fetcher);
    const controller = new AbortController();
    expect(await getC04Lookup(key, controller.signal)).toEqual(document);
    const [url, options] = fetcher.mock.calls[0];
    const parsed = new URL(url, "http://localhost");
    expect(parsed.pathname).toBe("/api/v1/c04/lookup");
    expect(Object.fromEntries(parsed.searchParams)).toEqual(key);
    expect(options).toMatchObject({ method: "GET", signal: controller.signal });
  });

  it.each([
    { ...document, source_id: "wrong-source" },
    { ...document, version: "wrong-version" },
    { ...document, chunk_id: "wrong-chunk" },
    { ...document, definitive_answer_allowed: undefined },
  ])("불일치하거나 불완전한 문서를 거부한다", async (data) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...envelope([]), data }))));
    await expect(getC04Lookup(key)).rejects.toThrow("Malformed or mismatched C04 document");
  });
});

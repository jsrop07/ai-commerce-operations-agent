import { describe, expect, it } from "vitest";
import * as fixtures from "../src/mocks/fixtures";

const forbiddenPatterns = [
  /[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/,
  /01[016789]-?\d{3,4}-?\d{4}/,
  /(?:api[_-]?key|secret|password|credential)\s*[:=]\s*["'][^"']+/i,
  /-----BEGIN (?:RSA |EC )?PRIVATE KEY-----/,
];

describe("synthetic fixture safety", () => {
  it("contains no PII or secret patterns", () => {
    const serialized = JSON.stringify(fixtures);
    for (const pattern of forbiddenPatterns) expect(serialized).not.toMatch(pattern);
  });

  it("uses explicit synthetic identifiers", () => {
    const serialized = JSON.stringify(fixtures);
    expect(serialized).toContain("demo_store");
    expect(serialized).toContain("sku_demo_001");
    expect(serialized).toContain("ord_demo_001");
    expect(serialized).toContain("ins_demo_001");
  });
});

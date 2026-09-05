import { expect, test, type Page } from "@playwright/test";

function collectWriteRequests(page: Page) {
  const writeRequests: string[] = [];

  page.on("request", (request) => {
    const method = request.method();

    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      writeRequests.push(`${method} ${request.url()}`);
    }
  });

  return writeRequests;
}

test("Day 6 Demo Mapping은 자동 선택 없이 키보드 선택·해제와 로컬 저장만 제공한다", async ({
  page,
}) => {
  const writeRequests = collectWriteRequests(page);

  await page.goto("http://127.0.0.1:30080/settings");
  await expect(page.getByTestId("route-settings")).toBeVisible();

  const multiCandidateItem = page
    .locator(".mapping-review-item")
    .filter({ hasText: "Synthetic Game Korean Edition" });
  const singleCandidateItem = page
    .locator(".mapping-review-item")
    .filter({ hasText: "Synthetic Card Game Standard" });
  const noCandidateItem = page
    .locator(".mapping-review-item")
    .filter({ hasText: "Unknown Synthetic Product" });

  const multiCandidate = multiCandidateItem.getByRole("button", {
    name: /sku_demo_001/,
  });
  const singleCandidate = singleCandidateItem.getByRole("button", {
    name: /sku_demo_002/,
  });

  await expect(multiCandidate).toHaveAttribute("aria-pressed", "false");
  await expect(singleCandidate).toHaveAttribute("aria-pressed", "false");
  await expect(noCandidateItem).toContainText("미연결 상태로 유지합니다");

  await multiCandidate.focus();
  await multiCandidate.press("Space");
  await expect(multiCandidate).toHaveAttribute("aria-pressed", "true");

  await multiCandidate.press("Space");
  await expect(multiCandidate).toHaveAttribute("aria-pressed", "false");

  await multiCandidate.press("Enter");
  await multiCandidateItem
    .getByRole("button", { name: "Demo 검토 결정 저장" })
    .click();
  await expect(multiCandidateItem).toContainText(
    "Demo 검토 결정이 저장되었습니다",
  );

  expect(writeRequests).toEqual([]);
});

test("Day 6 Production Read-Only는 Mapping 저장을 차단하고 품질 제외 규칙을 유지한다", async ({
  page,
}) => {
  const writeRequests = collectWriteRequests(page);

  await page.goto(
    "http://127.0.0.1:30080/settings?environment=production-read",
  );

  const mappingItem = page
    .locator(".mapping-review-item")
    .filter({ hasText: "Synthetic Game Korean Edition" });
  await mappingItem.getByRole("button", { name: /sku_demo_001/ }).click();
  await expect(
    mappingItem.getByRole("button", { name: "Demo 검토 결정 저장" }),
  ).toBeDisabled();
  await expect(mappingItem).toContainText(
    "Production Read-Only에서는 저장할 수 없으며",
  );

  const qualityOverview = page.locator(".quality-overview");
  await expect(qualityOverview).toContainText("확정 재고 합계: 12");

  for (const label of [
    "업무 사용 가능",
    "상품 연결 필요",
    "격리됨",
    "원천 품질 차단",
  ]) {
    await expect(qualityOverview.getByText(label, { exact: true })).toBeVisible();
  }

  const ecountQuality = qualityOverview
    .locator("article")
    .filter({ hasText: "ECOUNT" });
  await expect(ecountQuality).toContainText("재고값 사용 불가");
  await expect(ecountQuality).not.toContainText("원천 수량: 0");

  expect(writeRequests).toEqual([]);
});

test("Day 6 Inventory 최신성과 상세 패널 keyboard/focus 회귀를 유지한다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:30080/inventory?environment=production-read",
  );
  await expect(page.getByTestId("route-inventory")).toBeVisible();
  await expect(page.getByTestId("inventory-stale-warning")).toBeVisible();
  await expect(page.getByText(/오래됨/).first()).toBeVisible();
  await expect(
    page.getByText(/최신성 기준을 초과한 데이터입니다/).first(),
  ).toBeVisible();

  const row = page.getByRole("row", {
    name: /sku_demo_001 ECOUNT 재고 상세 열기/,
  });

  await row.focus();
  await row.press("Enter");

  const dialog = page.getByRole("dialog", { name: "sku_demo_001" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "재고 상세 닫기" })).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(row).toBeFocused();
});

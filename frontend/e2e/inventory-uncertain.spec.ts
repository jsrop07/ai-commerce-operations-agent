import { expect, test } from "@playwright/test";

test("D08-FE-03 stale 재고는 확정 재고처럼 오표현하지 않는다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/inventory?environment=production-read",
  );

  await expect(
    page.getByTestId("route-inventory"),
  ).toBeVisible();

  await expect(
    page.getByTestId("inventory-stale-warning"),
  ).toBeVisible();

  const staleRow = page
    .getByRole("row")
    .filter({
      hasText: "ECOUNT",
    })
    .first();

  await expect(staleRow).toBeVisible();

  await expect(
    staleRow.getByText(
      /확정 재고 합계에서 제외|확정 재고 합계 포함 여부 미제공/,
    ),
  ).toBeVisible();
});

test("D08-FE-03 null 재고 계약값은 0으로 표시하지 않는다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/inventory?environment=production-read",
  );

  await expect(
    page.getByTestId("route-inventory"),
  ).toBeVisible();

  const rows = page.locator("tbody tr");
  await expect(rows.first()).toBeVisible();

  const bodyText =
    (await rows.first().textContent()) ?? "";

  expect(bodyText).toContain("미제공");
});

test("D08-FE-03 source quality blocked 재고는 확정값으로 표현하지 않는다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/settings?environment=production-read",
  );

  await expect(
    page.getByTestId("route-settings"),
  ).toBeVisible();

  const qualityOverview =
    page.locator(".quality-overview");

  await expect(
    qualityOverview,
  ).toBeVisible();

  const ecountQuality =
    qualityOverview
      .locator("article")
      .filter({ hasText: "ECOUNT" });

  await expect(
    ecountQuality,
  ).toBeVisible();

  await expect(
    ecountQuality,
  ).not.toContainText("재고: 0");
});

test("D08-FE-03 uncertain 상태 확인 중 Production write는 발생하지 않는다", async ({
  page,
}) => {
  const writeRequests: string[] = [];

  page.on("request", (request) => {
    if (
      ["POST", "PUT", "PATCH", "DELETE"].includes(
        request.method(),
      )
    ) {
      writeRequests.push(
        `${request.method()} ${request.url()}`,
      );
    }
  });

  await page.goto(
    "http://127.0.0.1:5173/inventory?environment=production-read",
  );

  await expect(
    page.getByTestId("route-inventory"),
  ).toBeVisible();

  expect(writeRequests).toEqual([]);
});
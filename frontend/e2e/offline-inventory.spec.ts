import { expect, test } from "@playwright/test";

test("D08-FE-01 실제 오프라인 판매 Insight가 Frontend에 표시된다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/insights",
  );

  await expect(
    page.getByTestId("route-insights"),
  ).toBeVisible();

  const insight = page
    .getByTestId("real-backend-insight")
    .filter({
      hasText:
        "오프라인 판매가 예상 재고에 반영되었습니다.",
    });

  await expect(insight).toBeVisible();

  await expect(insight).toContainText(
    "Severity: LOW",
  );

  await expect(insight).toContainText(
    "Confidence: 1",
  );

  await expect(
    insight.getByTestId("insight-calculation"),
  ).toContainText(
    "시작 재고: 8 / 판매: 2 / 예상 재고: 6",
  );
});

test("D08-FE-01 실제 Inventory Projection 미제공 상태를 빈 데이터로 표시한다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/inventory",
  );

  await expect(
    page.getByTestId("route-inventory"),
  ).toBeVisible();

  await expect(
    page.getByText("표시할 재고가 없습니다"),
  ).toBeVisible();

  await expect(
    page.getByText(
      "현재 조회 가능한 재고 Snapshot이 없습니다.",
    ),
  ).toBeVisible();
});

test("D08-FE-01 실제 조회 흐름에서 Frontend Production write는 발생하지 않는다", async ({
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
    "http://127.0.0.1:5173/insights",
  );

  await expect(
    page.getByTestId("real-backend-insight"),
  ).toBeVisible();

  await page.goto(
    "http://127.0.0.1:5173/inventory",
  );

  await expect(
    page.getByTestId("route-inventory"),
  ).toBeVisible();

  expect(writeRequests).toEqual([]);
});
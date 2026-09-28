import { expect, test } from "@playwright/test";

test("D09-FE-01 실제 예약 위험 Projection의 fail-closed empty 상태를 표시한다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/orders",
  );

  await expect(
    page.getByTestId("route-orders"),
  ).toBeVisible();

  await expect(
    page.getByTestId("reservation-warning"),
  ).toContainText(
    "RESERVATION_RISK_EMPTY",
  );

  await expect(
    page.getByTestId("reservation-list-empty"),
  ).toContainText(
    "현재 확정 가능한 예약 위험 Projection이 없습니다.",
  );

  await expect(
    page.getByTestId("reservation-list-empty"),
  ).toContainText(
    "확인되지 않은 값을 0으로 표시하지 않습니다.",
  );
});

test("D09-FE-01 실제 예약 위험 응답이 비어 있을 때 Fixture row를 표시하지 않는다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/orders",
  );

  await expect(
    page.getByTestId("route-orders"),
  ).toBeVisible();

  await expect(
    page.getByTestId("reservation-risk-row"),
  ).toHaveCount(0);

  await expect(
    page.getByText("테스트 Fixture"),
  ).toHaveCount(0);
});

test("D09-FE-01 실제 예약 위험 조회에서 외부 write가 발생하지 않는다", async ({
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
    "http://127.0.0.1:5173/orders",
  );

  await expect(
    page.getByTestId("route-orders"),
  ).toBeVisible();

  await expect(
    page.getByTestId("reservation-list-empty"),
  ).toBeVisible();

  expect(writeRequests).toEqual([]);
});
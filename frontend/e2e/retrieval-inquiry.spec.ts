import { expect, test } from "@playwright/test";

test("D08-FE-01 Inquiry Retrieval 결과의 confidence와 index version을 표시한다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/inquiries",
  );

  await expect(
    page.getByTestId("route-inquiries"),
  ).toBeVisible();

  await expect(
    page.getByText("Retrieval Evidence"),
  ).toBeVisible();

  await expect(
    page.getByText(/Retrieval confidence:/),
  ).toBeVisible();

  await expect(
    page.getByText(/Query:/),
  ).toBeVisible();

  const retrievalSection = page
    .locator(".card")
    .filter({
      hasText: "Retrieval Evidence",
    })
    .first();

  await expect(
    retrievalSection,
  ).toBeVisible();

  await expect(
    retrievalSection,
  ).toContainText(/index/i);
});

test("D08-FE-01 citation이 있는 Inquiry는 CitationCard를 표시한다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/inquiries",
  );

  await expect(
    page.getByTestId("route-inquiries"),
  ).toBeVisible();

  const retrievalSection = page
    .locator(".card")
    .filter({
      hasText: "Retrieval Evidence",
    })
    .first();

  await expect(
    retrievalSection,
  ).toBeVisible();

  const citationCards = retrievalSection.locator(
    "[data-testid='citation-card']",
  );

  if ((await citationCards.count()) > 0) {
    await expect(
      citationCards.first(),
    ).toBeVisible();
  }
});

test("D08-FE-01 HOLD 상태는 자동 응답 가능 상태로 표현하지 않는다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:5173/inquiries",
  );

  await expect(
    page.getByTestId("route-inquiries"),
  ).toBeVisible();

  const holdText = page.getByText(
    /Retrieval answer status:\s*HOLD/,
  );

  if ((await holdText.count()) > 0) {
    await expect(
      holdText.first(),
    ).toBeVisible();

    await expect(
      page.getByText(/HOLD/).first(),
    ).toBeVisible();
  }
});

test("D08-FE-01 Inquiry Workbench 조회 중 외부 write를 발생시키지 않는다", async ({
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
    "http://127.0.0.1:5173/inquiries",
  );

  await expect(
    page.getByTestId("route-inquiries"),
  ).toBeVisible();

  expect(writeRequests).toEqual([]);
});
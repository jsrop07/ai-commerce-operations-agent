import { expect, test } from "@playwright/test";

test("D04-FE-02 PRODUCTION_READ에서는 조회를 허용하고 금지 CTA와 write 요청이 없다", async ({
  page,
}) => {
  const methods: string[] = [];
  const writeRequests: string[] = [];

  page.on("request", (request) => {
    const method = request.method();
    methods.push(method);

    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      writeRequests.push(`${method} ${request.url()}`);
    }
  });

  await page.goto(
    "http://127.0.0.1:30080/?environment=production-read",
  );
  await expect(page.getByTestId("route-dashboard")).toBeVisible();

  const banner = page.getByRole("banner");
  await expect(banner).toContainText("Production Read-Only");
  await expect(banner).toContainText("조회와 내부 확인 업무만 사용할 수 있습니다");

  const prohibitedCtas = [
    "실제 재고 수정",
    "주문 취소",
    "환불 실행",
    "가격 변경",
    "결제",
    "정산",
    "고객 답변 실제 전송",
  ];

  for (const label of prohibitedCtas) {
    await expect(
      page.getByRole("button", { name: label, exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: label, exact: true }),
    ).toHaveCount(0);
  }

  await expect(page.getByText("오늘 할 일", { exact: true })).toBeVisible();
  await expect(page.getByText("업무 생성 제안", { exact: true })).toBeVisible();

  expect(methods).toContain("GET");
  expect(writeRequests).toEqual([]);
});
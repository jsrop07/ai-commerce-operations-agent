import { expect, test } from "@playwright/test";

test("D04-FE-03 Provider 하나가 실패해도 정상 데이터와 stale 정보는 유지된다", async ({
  page,
}) => {
  await page.goto(
    "http://127.0.0.1:30080/?degraded=true",
  );

  await expect(page.getByTestId("route-dashboard")).toBeVisible();

  const failure = page.getByTestId("provider-partial-failure");
  await expect(failure).toBeVisible();
  await expect(failure).toContainText("일부 연동 데이터를 불러오지 못했습니다.");
  await expect(failure).toContainText("실패 대상: ECOUNT");
  await expect(failure).toContainText("사유: 응답 시간 초과");
  await expect(failure).not.toContainText("TIMEOUT");
  await expect(
    failure.locator('time[datetime="2026-09-03T10:30:00Z"]'),
  ).toBeVisible();

  const providerStatus = page.getByRole("region", { name: "연동 상태" });
  await expect(providerStatus).toContainText("CAFE24");
  await expect(providerStatus).toContainText("TOSS_POS");
  await expect(providerStatus.getByText("● 최신", { exact: true })).toHaveCount(2);
  await expect(providerStatus).toContainText("ECOUNT");
  await expect(providerStatus.getByText("▲ 오래됨", { exact: true })).toBeVisible();

  await expect(page.getByText("▲ eCount 데이터 확인 필요")).toBeVisible();
  await expect(page.getByRole("heading", { name: "긴급 Queue" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "오늘 할 일" })).toBeVisible();
  await expect(page.getByTestId("system-state-loading")).toHaveCount(0);

  const opener = page.getByRole("button", {
    name: "예약 재고 부족 판단 근거 보기",
  });
  await opener.focus();
  await opener.press("Enter");

  const dialog = page.getByRole("dialog", { name: "예약 재고 부족" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute("aria-modal", "true");

  const closeButton = dialog.getByRole("button", {
    name: "판단 근거 패널 닫기",
  });
  await expect(closeButton).toBeFocused();
  await closeButton.press("Tab");
  await expect(closeButton).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();

  await opener.press("Space");
  await expect(page.getByRole("dialog", { name: "예약 재고 부족" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(opener).toBeFocused();
});
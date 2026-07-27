import { expect, test, type Page } from "@playwright/test";

interface RunPage {
  page: {
    total: number;
  };
}

const runRows = (page: Page) => page.locator("table tbody tr");

test("실 카탈로그에서 필터·정렬·페이지·요약 이동·비교 담기가 동작한다", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/runs$/);
  await expect(page.getByRole("heading", { name: "카탈로그 · 실행" })).toBeVisible();
  await expect(runRows(page).first()).toBeVisible();

  const totalLabel = page.locator("p").filter({ hasText: /개 실행/ }).first();
  const initialTotalText = await totalLabel.innerText();
  const initialTotal = Number(initialTotalText.replace(/[^\d]/g, ""));
  const initialPageCount = Math.ceil(initialTotal / 50);
  expect(initialTotal).toBeGreaterThan(1);
  expect(initialPageCount).toBeGreaterThan(1);
  expect(await runRows(page).count()).toBeGreaterThan(0);

  const statusOptions = ["RUNNING", "COMPLETED", "EVALUATED", "FAILED", "ORPHANED"];
  let narrowingStatus: string | undefined;
  let narrowedTotal = initialTotal;
  for (const status of statusOptions) {
    const response = await request.get(
      `/api/v1/runs?limit=1&status=${encodeURIComponent(status)}`,
    );
    expect(response.ok()).toBeTruthy();
    const body = (await response.json()) as RunPage;
    if (body.page.total > 0 && body.page.total < initialTotal) {
      narrowingStatus = status;
      narrowedTotal = body.page.total;
      break;
    }
  }
  expect(narrowingStatus, "실데이터를 줄이는 상태 필터가 있어야 한다").toBeTruthy();

  await page.getByLabel("실행 상태 필터").selectOption(narrowingStatus!);
  await expect(totalLabel).toContainText(narrowedTotal.toLocaleString());
  expect(narrowedTotal).toBeLessThan(initialTotal);
  await expect(runRows(page).first()).toBeVisible();

  await page.getByRole("button", { name: "초기화" }).click();
  await expect(totalLabel).toContainText(initialTotal.toLocaleString());

  const sortedResponse = page.waitForResponse((response) => {
    if (!response.url().includes("/api/v1/runs?") || response.status() !== 200) {
      return false;
    }
    return new URL(response.url()).searchParams.get("sort")?.replace("-", "") === "pf";
  });
  await page.getByRole("button", { name: "PF" }).click();
  await sortedResponse;
  await expect(runRows(page).first()).toBeVisible();

  const pageIndicator = page.locator("span").filter({ hasText: /^\d+ \/ \d+$/ });
  await expect(pageIndicator).toHaveText(`1 / ${initialPageCount}`);
  const nextResponse = page.waitForResponse((response) => {
    if (!response.url().includes("/api/v1/runs?") || response.status() !== 200) {
      return false;
    }
    return new URL(response.url()).searchParams.get("offset") === "50";
  });
  await page.getByRole("button", { name: "다음" }).click();
  await nextResponse;
  await expect(pageIndicator).toHaveText(`2 / ${initialPageCount}`);
  await expect(runRows(page).first()).toBeVisible();

  const firstCheckbox = runRows(page).first().locator('input[type="checkbox"]');
  await firstCheckbox.check();
  await expect(page.getByText("선택 1개", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "비교에 담기" }).click();
  await expect(page.getByRole("button", { name: "비교 (1)" })).toBeVisible();

  await runRows(page).first().click();
  await expect(page).toHaveURL(/\/runs\/BT_/);
  await expect(page.locator("h1").filter({ hasText: /^BT_/ })).toBeVisible();
});

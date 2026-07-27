import { expect, test } from "@playwright/test";

interface CatalogRun {
  pf: number | null;
}

interface CatalogResponse {
  data: CatalogRun[];
}

test("카탈로그의 실 실행 2건을 전치 비교하고 기준선·지표 델타를 표시한다", async ({
  page,
  request,
}) => {
  const catalogResponse = await request.get(
    "/api/v1/runs?limit=50&offset=0&sort=-created_at",
  );
  expect(catalogResponse.ok()).toBeTruthy();
  const catalog = (await catalogResponse.json()) as CatalogResponse;
  const comparableIndexes = catalog.data
    .map((run, index) => ({ run, index }))
    .filter(({ run }) => run.pf !== null)
    .slice(0, 2)
    .map(({ index }) => index);
  expect(comparableIndexes).toHaveLength(2);

  await page.goto("/runs");
  const rows = page.locator("table tbody tr");
  await expect(rows.first()).toBeVisible();
  for (const index of comparableIndexes) {
    await rows.nth(index).locator('input[type="checkbox"]').check();
  }
  await expect(page.getByText("선택 2개", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "비교에 담기" }).click();
  await expect(page.getByRole("button", { name: "비교 (2)" })).toBeVisible();

  await page.getByRole("button", { name: "비교 (2)" }).click();
  await page.getByRole("button", { name: "비교 열기" }).click();
  await expect(page).toHaveURL(/\/compare$/);
  await expect(page.getByRole("heading", { name: "실행 비교 (2)" })).toBeVisible();
  await expect(page.getByLabel("비교 기준선")).toBeVisible();
  await expect(page.getByText("기준선", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "설정 diff + 지표 델타" })).toBeVisible();

  const comparisonTable = page.locator("table").first();
  await expect(comparisonTable).toBeVisible();
  expect(await comparisonTable.locator("thead th").count()).toBe(3);
  expect(await comparisonTable.locator("tbody tr td:first-child").count()).toBeGreaterThan(3);
  await expect(
    comparisonTable.locator("tbody td").filter({ hasText: /\([+-]?\d/ }).first(),
  ).toBeVisible();
});

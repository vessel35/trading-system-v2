import { expect, test } from "@playwright/test";

const REAL_EVIDENCE_RUN_ID = "BT_20260725_000976_p1-seed-btc-60d";

test("실 실행 요약이 정체성·판정·지표·건강도·비용을 저장값으로 표시한다", async ({
  page,
}) => {
  await page.goto(`/runs/${REAL_EVIDENCE_RUN_ID}`);

  await expect(page.getByRole("heading", { name: REAL_EVIDENCE_RUN_ID })).toBeVisible();
  await expect(
    page.getByText(
      /VesselReference v\d+\.\d+\.\d+ · BTC\/USDT:USDT · 1h · FUTURES/,
    ),
  ).toBeVisible();
  await expect(page.getByText("vessel-reference", { exact: true })).toBeVisible();

  await expect(page.getByText("GATE", { exact: true })).toBeVisible();
  await expect(page.getByText("ROUTE", { exact: true })).toBeVisible();
  await expect(page.getByText("ENVELOPE", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "핵심 지표" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "데이터 건강도" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "비용 분해" })).toBeVisible();

  for (const label of ["PF", "Sortino", "MDD", "Trades"]) {
    const tile = page.getByText(label, { exact: true }).first().locator("..");
    const value = tile.locator("p").nth(1);
    await expect(value).toHaveText(/\S+/);
    await expect(value).not.toHaveText("—");
  }

  for (const label of ["Coverage", "Integrity", "Gross PnL", "Net PnL"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText("실행 요약을 열 수 없습니다.")).toHaveCount(0);
});

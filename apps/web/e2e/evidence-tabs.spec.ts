import { expect, test, type Page } from "@playwright/test";

const REAL_EVIDENCE_RUN_ID = "BT_20260725_000976_p1-seed-btc-60d";

async function expectLiveTab(page: Page, tabName: string | RegExp) {
  const tab = page.getByRole("tab", { name: tabName });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-selected", "true");
  const panel = page.getByRole("tabpanel").first();
  await expect(panel).toBeVisible();
  await expect
    .poll(async () => (await panel.innerText()).trim().length)
    .toBeGreaterThan(20);
  await expect(page.getByText("이 Evidence 탭을 표시하지 못했습니다.")).toHaveCount(0);
  await expect(page.getByText("화면을 표시하는 중 문제가 발생했습니다.")).toHaveCount(0);
  return panel;
}

test("Evidence 실 SQLite의 7개 탭이 차트·표·정직한 유보 상태로 완주한다", async ({
  page,
}) => {
  const pageErrors: Error[] = [];
  page.on("pageerror", (error) => pageErrors.push(error));

  await page.goto(`/runs/${REAL_EVIDENCE_RUN_ID}`);
  await expect(page.getByRole("heading", { name: REAL_EVIDENCE_RUN_ID })).toBeVisible();

  let panel = await expectLiveTab(page, "개요");
  await expect(panel.getByRole("heading", { name: "핵심 지표" })).toBeVisible();

  panel = await expectLiveTab(page, "자본곡선·DD");
  await expect(panel.getByRole("heading", { name: "자본곡선" })).toBeVisible();
  await expect(panel.getByLabel("자본곡선").locator("canvas").first()).toBeVisible();
  await expect(panel.getByRole("heading", { name: "드로다운 사건" })).toBeVisible();

  panel = await expectLiveTab(page, "거래");
  await expect(panel.getByText(/거래 [\d,]+건/).first()).toBeVisible();
  await expect(panel.getByRole("heading", { name: "거래 목록" }).first()).toBeVisible();
  await expect(panel.locator("svg").first()).toBeVisible();

  panel = await expectLiveTab(page, "차트");
  await expect(
    panel.getByRole("heading", { name: "시장 구조 · 캔들 + 저장 지표" }),
  ).toBeVisible();
  await expect(panel.getByLabel("시장 캔들 차트").locator("canvas").first()).toBeVisible();

  panel = await expectLiveTab(page, "신호·의사결정");
  await expect(panel.getByText(/신호 [\d,]+ · 판단 [\d,]+/)).toBeVisible();
  await expect(panel.getByRole("heading", { name: "판단 타임라인" })).toBeVisible();
  await expect(panel.locator("table").first()).toBeVisible();
  await panel.getByRole("tab", { name: /^놓친 기회/ }).click();
  await expect(
    panel.getByText(/놓친 기회\(MISSED_OPPORTUNITY\).*미구현.*유보되었습니다\(3차\)/),
  ).toBeVisible();

  panel = await expectLiveTab(page, "무결성·비용");
  await expect(panel.getByRole("heading", { name: "무결성 검사" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "데이터 커버리지" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "비용 워터폴" })).toBeVisible();
  await expect(panel.locator("svg").first()).toBeVisible();

  panel = await expectLiveTab(page, "조건부·노트");
  await expect(
    panel.getByText(/조건부 기대값은 미구현·유보 상태입니다/),
  ).toBeVisible();
  await expect(
    panel.getByText(/연구 노트\(FINDING_CLAIM\).*미구현.*유보되었습니다\(3차\)/),
  ).toBeVisible();

  expect(pageErrors, pageErrors.map((error) => error.message).join("\n")).toEqual([]);
});

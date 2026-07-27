import { expect, test } from "@playwright/test";

test("실행·스윕·사전등록 폼은 잘못된 실행 이름을 네이티브 검증에서 차단한다", async ({
  page,
}) => {
  const nonReadRequests: string[] = [];
  page.on("request", (request) => {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      nonReadRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await page.goto("/manage");
  await expect(page.getByRole("heading", { name: "실행 관리" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "새 백테스트 트리거" })).toBeVisible();
  await expect(page.getByText("DRY-RUN · 실주문 아님")).toBeVisible();

  const runName = page.getByLabel(/실행 이름/);
  await runName.fill("Invalid Run");
  const validity = await runName.evaluate((element: HTMLInputElement) => ({
    valid: element.validity.valid,
    patternMismatch: element.validity.patternMismatch,
  }));
  expect(validity).toEqual({ valid: false, patternMismatch: true });

  const trigger = page.getByRole("button", { name: "트리거(모의)", exact: true });
  const sweepTrigger = page.getByRole("button", {
    name: "스윕 트리거(모의)",
    exact: true,
  });
  await expect(trigger).toBeEnabled();
  await expect(sweepTrigger).toBeEnabled();

  await trigger.click();
  await expect(runName).toBeFocused();
  await expect(runName).toHaveValue("Invalid Run");

  await page.getByLabel(/^실행 제출 메타데이터/).check();
  await expect(page.getByText(/사전등록 잠금은 .*유보\(3차\)/)).toBeVisible();
  await expect(page.getByRole("textbox", { name: "가설", exact: true })).toBeVisible();
  await sweepTrigger.click();
  await expect(runName).toBeFocused();

  await page.getByRole("button", { name: "설정 검증" }).click();
  await expect(runName).toBeFocused();
  await page.waitForTimeout(300);
  expect(nonReadRequests, "잘못된 폼은 POST를 한 건도 만들면 안 된다").toEqual([]);
  await expect(page.getByText(/\bjob\b.*등록되었습니다/)).toHaveCount(0);
});

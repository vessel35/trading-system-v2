import { describe, expect, it } from "vitest";

import {
  formatChartTime,
  formatPeriod,
  formatTimestamp,
  fromDisplayZoneInput,
  toDisplayZoneInput,
} from "./utils";

describe("표시 시간대", () => {
  it("UTC로 저장된 시각을 KST로 보여 준다", () => {
    // 2026-01-01T00:00Z is 09:00 on the same day in Seoul. The day-period word
    // comes from the runtime's locale data — a Node build without full ICU says
    // "AM" where a complete one says "오전" — so the assertion pins the converted
    // instant instead of the wording.
    expect(formatTimestamp("2026-01-01T00:00:00Z")).toMatch(
      /^2026\. 1\. 1\. (오전|AM) 9:00$/,
    );
    // 2026-01-01T15:00Z has already crossed midnight in Seoul.
    expect(formatPeriod("2026-01-01T15:00:00Z", "2026-01-02T15:00:00Z")).toBe(
      "26. 01. 02. → 26. 01. 03.",
    );
    expect(formatChartTime(Date.parse("2026-01-01T00:00:00Z") / 1_000)).toBe(
      "01. 01. 09:00",
    );
  });

  it("입력 필드의 KST 벽시계와 UTC 순간을 서로 변환한다", () => {
    expect(toDisplayZoneInput("2025-12-31T15:00:00Z")).toBe("2026-01-01T00:00");
    expect(fromDisplayZoneInput("2026-01-01T00:00").toISOString()).toBe(
      "2025-12-31T15:00:00.000Z",
    );
  });

  it("두 변환이 서로를 되돌린다", () => {
    const wallClock = "2026-07-30T13:45";
    expect(toDisplayZoneInput(fromDisplayZoneInput(wallClock).toISOString())).toBe(
      wallClock,
    );
  });

  it("형식이 잘못된 값은 빈 문자열과 잘못된 시각으로 답한다", () => {
    expect(toDisplayZoneInput("not-a-time")).toBe("");
    expect(Number.isNaN(fromDisplayZoneInput("not-a-time").getTime())).toBe(true);
  });
});

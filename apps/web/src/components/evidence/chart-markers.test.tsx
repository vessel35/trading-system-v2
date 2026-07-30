import { describe, expect, it } from "vitest";

import { entryStyle, exitStyle } from "./chart-tab";

describe("차트 거래 마커", () => {
  it("진입 마커는 방향을 밝힌다", () => {
    expect(entryStyle("LONG").label).toBe("롱 진입");
    expect(entryStyle("SHORT").label).toBe("숏 진입");
    // Direction must also be readable without colour vision.
    expect(entryStyle("LONG").color).not.toBe(entryStyle("SHORT").color);
  });

  it("청산 마커는 익절과 손절을 구분한다", () => {
    expect(exitStyle("TAKE_PROFIT").label).toBe("익절");
    expect(exitStyle("STOP_LOSS").label).toBe("손절");
    expect(exitStyle("LIQUIDATION").label).toBe("강제청산");
    expect(exitStyle("TAKE_PROFIT").color).not.toBe(exitStyle("STOP_LOSS").color);
  });

  it("기록된 모든 청산 사유에 이름이 있다", () => {
    const recorded = [
      "STOP_LOSS",
      "TAKE_PROFIT",
      "TRAILING_STOP",
      "LIQUIDATION",
      "SIGNAL_EXIT",
      "REVERSAL",
      "DATA_GAP",
      "END_OF_DATA",
    ];
    for (const reason of recorded) {
      expect(exitStyle(reason).label).not.toBe("청산");
    }
  });

  it("사유가 없는 청산은 사유를 지어내지 않는다", () => {
    expect(exitStyle(null).label).toBe("청산");
    expect(exitStyle("SOMETHING_NEW").label).toBe("청산");
  });
});

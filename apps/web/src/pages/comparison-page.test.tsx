import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunComparisonItem } from "../api/client";
import {
  flattenSettings,
  IndicatorVersionWarning,
  indicatorVersionMismatches,
  resolvedSeries,
} from "./comparison-page";

function comparisonItem(
  runName: string,
  version: string,
): RunComparisonItem {
  return {
    run: {
      run_name: runName,
      resolved_indicators_json: [
        { name: "EMA", params: { period: 9 }, version },
        { name: "pat_doji", params: {}, version: "2.0.0+talib.0.7.1" },
      ],
      params_json: {},
    },
    summary: null,
  } as unknown as RunComparisonItem;
}

describe("실행 비교의 지표 계산 판", () => {
  it("resolved 목록을 열쇠와 판의 쌍으로 복원한다", () => {
    expect(
      resolvedSeries([
        { name: "EMA", params: { period: 9 }, version: "1.0.0" },
        { name: "pat_doji", params: {}, version: "2.0.0+talib.0.7.1" },
      ]),
    ).toEqual([
      { key: "EMA(period=9)", version: "1.0.0" },
      { key: "pat_doji", version: "2.0.0+talib.0.7.1" },
    ]);
  });

  it("설정 평탄화가 열쇠 뒤에 계산 판을 함께 표시한다", () => {
    const settings = flattenSettings(comparisonItem("첫 실행", "1.0.0"));

    expect(settings["indicator.EMA(period=9)"]).toBe(
      "EMA(period=9) (1.0.0)",
    );
    expect(settings["indicator.pat_doji"]).toBe(
      "pat_doji (2.0.0+talib.0.7.1)",
    );
  });

  it("같은 열쇠의 판이 다르면 실행 이름과 각 판을 눈에 띄게 경고한다", () => {
    const mismatches = indicatorVersionMismatches([
      comparisonItem("기준 실행", "1.0.0"),
      comparisonItem("비교 실행", "2.0.0"),
    ]);

    expect(mismatches).toHaveLength(1);
    render(<IndicatorVersionWarning mismatches={mismatches} />);
    const warning = screen.getByRole("alert");
    expect(warning).toHaveTextContent("같은 지표 열쇠");
    expect(warning).toHaveTextContent("EMA(period=9)");
    expect(warning).toHaveTextContent("기준 실행 (1.0.0)");
    expect(warning).toHaveTextContent("비교 실행 (2.0.0)");
  });
});

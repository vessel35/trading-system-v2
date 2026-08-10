import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunComparisonItem } from "../api/client";
import {
  EquityOverlap,
  fetchEquity,
  flattenSettings,
  IndicatorVersionWarning,
  indicatorVersionMismatches,
  resolvedSeries,
} from "./comparison-page";
import { server } from "../test/server";

const chartHarness = vi.hoisted(() => ({
  setData: vi.fn(),
}));

vi.mock("lightweight-charts", () => ({
  ColorType: { Solid: "Solid" },
  LineSeries: "LineSeries",
  createChart: () => ({
    addSeries: () => ({ setData: chartHarness.setData }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
  }),
}));

function comparisonItem(
  runName: string,
  version: string,
): RunComparisonItem {
  return {
    run: {
      run_name: runName,
      resolved_indicators_json: [
        { name: "EMA", params: { period: 9 }, timeframe: "1h", version },
        { name: "pat_doji", params: {}, timeframe: "1h", version: "2.0.0+talib.0.7.1" },
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
        { name: "EMA", params: { period: 9 }, timeframe: "1h", version: "1.0.0" },
        { name: "pat_doji", params: {}, timeframe: "4h", version: "2.0.0+talib.0.7.1" },
      ]),
    ).toEqual([
      { key: "ema:period=9@1h", version: "1.0.0" },
      { key: "pat_doji@4h", version: "2.0.0+talib.0.7.1" },
    ]);
  });

  it("설정 평탄화가 열쇠 뒤에 계산 판을 함께 표시한다", () => {
    const settings = flattenSettings(comparisonItem("첫 실행", "1.0.0"));

    expect(settings["indicator.ema:period=9@1h"]).toBe(
      "ema:period=9@1h (1.0.0)",
    );
    expect(settings["indicator.pat_doji@1h"]).toBe(
      "pat_doji@1h (2.0.0+talib.0.7.1)",
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
    expect(warning).toHaveTextContent("ema:period=9@1h");
    expect(warning).toHaveTextContent("기준 실행 (1.0.0)");
    expect(warning).toHaveTextContent("비교 실행 (2.0.0)");
  });
});

describe("실행 비교의 자본곡선", () => {
  beforeEach(() => {
    chartHarness.setData.mockReset();
  });

  it("원본 자본 Evidence로 내려가도 같은 초에는 마지막 점만 남긴다", async () => {
    server.use(
      http.get("http://localhost/api/v1/runs/:runId/chart-summaries", () =>
        HttpResponse.json({
          data: [],
          page: {
            limit: 200,
            after_seq: 0,
            next_after_seq: null,
            total: 0,
            has_more: false,
          },
        }),
      ),
      http.get("http://localhost/api/v1/runs/:runId/equity", () =>
        HttpResponse.json({
          data: [
            {
              equity_seq: 1,
              ts: "2025-07-03T15:00:00.000Z",
              total_equity: "7994.92543575",
            },
            {
              equity_seq: 2,
              ts: "2025-07-03T15:00:00.001Z",
              total_equity: "7992.65787561",
            },
          ],
          page: {
            limit: 200,
            after_seq: 0,
            next_after_seq: null,
            total: 2,
            has_more: false,
          },
        }),
      ),
    );

    const points = await fetchEquity("fixture-comparison");

    expect(points).toEqual([
      {
        time: Date.parse("2025-07-03T15:00:00Z") / 1_000,
        value: 7_992.65787561,
      },
    ]);

    render(
      <EquityOverlap
        runs={[comparisonItem("비교 실행", "1.0.0")]}
        series={[points]}
      />,
    );
    await waitFor(() => expect(chartHarness.setData).toHaveBeenCalledWith(points));
  });
});

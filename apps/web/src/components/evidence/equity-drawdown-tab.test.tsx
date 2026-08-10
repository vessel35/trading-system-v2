import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChartSummary, EquityPoint } from "../../api/client";
import { renderWithQuery } from "../../test/render";
import { server } from "../../test/server";
import {
  drawdownSeriesFromEvidence,
  EquityDrawdownTab,
} from "./equity-drawdown-tab";

const chartHarness = vi.hoisted(() => ({
  setData: vi.fn(),
}));

vi.mock("lightweight-charts", () => ({
  AreaSeries: "AreaSeries",
  ColorType: { Solid: "Solid" },
  PriceScaleMode: { Logarithmic: 1, Normal: 0 },
  createChart: () => ({
    addSeries: () => ({ setData: chartHarness.setData }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
  }),
  createSeriesMarkers: vi.fn(),
}));

function cursor(data: unknown[]) {
  return {
    data,
    page: {
      limit: 200,
      after_seq: 0,
      next_after_seq: null,
      total: data.length,
      has_more: false,
    },
  };
}

function chartPoint(
  summarySeq: number,
  seriesName: "equity" | "drawdown",
  bucketTs: string,
  value: number,
) {
  return {
    summary_seq: summarySeq,
    run_id: "fixture-equity",
    series_name: seriesName,
    bucket_ts: bucketTs,
    value,
    payload_json: null,
  };
}

function useEquityHandlers(chart: unknown[]) {
  server.use(
    http.get("http://localhost/api/v1/runs/:runId/chart-summaries", () =>
      HttpResponse.json(cursor(chart)),
    ),
    http.get("http://localhost/api/v1/runs/:runId/executions", () =>
      HttpResponse.json(cursor([])),
    ),
    http.get("http://localhost/api/v1/runs/:runId/drawdown-episodes", () =>
      HttpResponse.json(cursor([])),
    ),
  );
}

describe("자본곡선 초 단위 충돌 복구", () => {
  beforeEach(() => {
    chartHarness.setData.mockReset();
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("1ms 차이인 끝 두 점을 접어 엄격 증가하는 시각만 setData에 넘긴다", async () => {
    useEquityHandlers([
      chartPoint(1, "equity", "2025-07-03T14:55:00.000Z", 8_010),
      chartPoint(2, "drawdown", "2025-07-03T14:55:00.000Z", -0.01),
      chartPoint(3, "equity", "2025-07-03T15:00:00.000Z", 7_994.92543575),
      chartPoint(4, "drawdown", "2025-07-03T15:00:00.000Z", -0.02),
      chartPoint(5, "equity", "2025-07-03T15:00:00.001Z", 7_992.65787561),
      chartPoint(6, "drawdown", "2025-07-03T15:00:00.001Z", -0.03),
    ]);

    renderWithQuery(
      <EquityDrawdownTab runId="fixture-equity" onSelectTrade={vi.fn()} />,
    );

    await waitFor(() => expect(chartHarness.setData).toHaveBeenCalledOnce());
    const points = chartHarness.setData.mock.calls[0][0] as Array<{
      time: number;
      value: number;
    }>;
    expect(points).toHaveLength(2);
    expect(points[1].value).toBe(7_992.65787561);
    expect(points.every((point, index) => index === 0 || points[index - 1].time < point.time))
      .toBe(true);
    expect(screen.getByText(/3개 저장 포인트/)).toHaveTextContent(
      "3개 저장 포인트 · 2개 그림 포인트 · 1개 접힘",
    );
  });

  it("겹침이 없으면 접힘 문구를 표시하지 않는다", async () => {
    useEquityHandlers([
      chartPoint(1, "equity", "2025-07-03T14:55:00.000Z", 8_010),
      chartPoint(2, "equity", "2025-07-03T15:00:00.000Z", 7_994.92543575),
    ]);

    renderWithQuery(
      <EquityDrawdownTab runId="fixture-equity" onSelectTrade={vi.fn()} />,
    );

    expect(await screen.findByText(/2개 저장 포인트/)).toHaveTextContent(
      "2개 저장 포인트 · 2개 그림 포인트",
    );
    expect(screen.queryByText(/접힘/)).not.toBeInTheDocument();
  });

  it("자본 차트가 실패해도 drawdown과 낙폭 사건 표를 남긴다", async () => {
    chartHarness.setData.mockImplementationOnce(() => {
      throw new Error("fixture chart failure");
    });
    useEquityHandlers([
      chartPoint(1, "equity", "2025-07-03T14:55:00.000Z", 8_010),
      chartPoint(2, "drawdown", "2025-07-03T14:55:00.000Z", -0.01),
    ]);

    renderWithQuery(
      <EquityDrawdownTab runId="fixture-equity" onSelectTrade={vi.fn()} />,
    );

    expect(
      await screen.findByText("이 자본곡선 차트를 표시하지 못했습니다."),
    ).toBeInTheDocument();
    expect(screen.getByText("드로다운")).toBeInTheDocument();
    expect(screen.getByText("드로다운 사건이 없습니다.")).toBeInTheDocument();
  });
});

describe("drawdown 계열 보존", () => {
  it("밀리초가 다른 점의 수와 시각과 값을 그대로 둔다", () => {
    const chart = [
      chartPoint(1, "drawdown", "2025-07-03T15:00:00.000Z", -0.02),
      chartPoint(2, "drawdown", "2025-07-03T15:00:00.001Z", -0.03),
    ] as ChartSummary[];

    expect(drawdownSeriesFromEvidence(chart, [])).toEqual([
      { ts: "2025-07-03T15:00:00.000Z", value: -2 },
      { ts: "2025-07-03T15:00:00.001Z", value: -3 },
    ]);
  });

  it("요약이 없을 때도 원본 drawdown 점을 그대로 둔다", () => {
    const equity = [
      {
        ts: "2025-07-03T15:00:00.000Z",
        drawdown_pct: -0.02,
      },
      {
        ts: "2025-07-03T15:00:00.001Z",
        drawdown_pct: -0.03,
      },
    ] as EquityPoint[];

    expect(drawdownSeriesFromEvidence([], equity)).toEqual([
      { ts: "2025-07-03T15:00:00.000Z", value: -2 },
      { ts: "2025-07-03T15:00:00.001Z", value: -3 },
    ]);
  });
});

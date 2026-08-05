import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { useChartEvidence } from "./use-evidence";

const OPEN_TIME = "2025-01-01T00:00:00Z";
const CLOSE_TIME = "2025-01-01T01:00:00Z";

function Probe({ selected }: { selected: ReadonlySet<string> | null }) {
  const evidence = useChartEvidence("fixture-lazy", selected);
  if (
    evidence.candles.isLoading ||
    evidence.definitions.isLoading ||
    evidence.indicators.isLoading
  ) {
    return <p>loading</p>;
  }
  const error =
    evidence.candles.error ??
    evidence.definitions.error ??
    evidence.indicators.error;
  if (error) throw error;
  return (
    <output aria-label="불러온 계열">
      {(evidence.indicators.data ?? [])
        .map((snapshot) => snapshot.indicator_key)
        .join(",")}
    </output>
  );
}

function lazyHandlers(requests: URL[]) {
  return [
    http.get("http://localhost/api/v1/runs/:runId/candles", () =>
      HttpResponse.json({
        data: [
          {
            open_time: OPEN_TIME,
            close_time: CLOSE_TIME,
            open: 100,
            high: 102,
            low: 99,
            close: 101,
            volume: 10,
            quote_volume: null,
            trade_count: null,
          },
        ],
        page: {
          limit: 5_000,
          total: 1,
          has_more: false,
          truncated: false,
          window_clamped: false,
          from_ts: OPEN_TIME,
          to_ts: CLOSE_TIME,
          timeframe: "1h",
          source_timeframe: "1m",
        },
      }),
    ),
    http.get("http://localhost/api/v1/runs/:runId/indicator-definitions", () =>
      HttpResponse.json([
        {
          indicator_key: "EMA(period=9)",
          indicator_name: "EMA",
          series_kind: "indicator",
          impl_version: "1.0.0",
        },
        {
          indicator_key: "pat_doji",
          indicator_name: "pat_doji",
          series_kind: "pattern",
          impl_version: "2.0.0+talib.0.7.1",
        },
      ]),
    ),
    http.get(
      "http://localhost/api/v1/runs/:runId/indicator-snapshots",
      ({ request }) => {
        const url = new URL(request.url);
        requests.push(url);
        const key = url.searchParams.get("indicator_key") ?? "";
        return HttpResponse.json({
          data: [
            {
              snapshot_seq: 1,
              run_id: "fixture-lazy",
              indicator_key: key,
              indicator_name: key.startsWith("pat_") ? key : "EMA",
              params_json: {},
              impl_version: key.startsWith("pat_")
                ? "2.0.0+talib.0.7.1"
                : "1.0.0",
              pinned_impl: true,
              series_kind: key.startsWith("pat_") ? "pattern" : "indicator",
              category: key.startsWith("pat_") ? "candlestick" : "trend",
              impl_note: "fixture",
              min_history: 1,
              computation_mode: "incremental",
              enabled_reason: "all",
              feature_ts: CLOSE_TIME,
              candle_open_time: OPEN_TIME,
              candle_close_time: CLOSE_TIME,
              value: key.startsWith("pat_") ? null : 101,
              value_json: key.startsWith("pat_")
                ? {
                    [key]: 1,
                    [`${key}_confirm`]: 0,
                    [`${key}_dir`]: 1,
                    [`${key}_strength`]: 1,
                  }
                : null,
              is_warmup: false,
            },
          ],
          page: {
            limit: 200,
            after_seq: 0,
            next_after_seq: null,
            total: 1,
            has_more: false,
          },
        });
      },
    ),
  ];
}

describe("차트 Evidence 지연 조회", () => {
  it("기본 상태에서는 정의 목록의 지표 값만 가져오고 패턴은 가져오지 않는다", async () => {
    const requests: URL[] = [];
    server.use(...lazyHandlers(requests));

    renderWithQuery(<Probe selected={null} />);

    expect(await screen.findByLabelText("불러온 계열")).toHaveTextContent(
      "EMA(period=9)",
    );
    expect(requests).toHaveLength(1);
    expect(requests[0].searchParams.get("indicator_key")).toBe("EMA(period=9)");
  });

  it("고른 패턴 하나만 현재 캔들 시간 구간으로 가져온다", async () => {
    const requests: URL[] = [];
    server.use(...lazyHandlers(requests));

    renderWithQuery(<Probe selected={new Set(["pat_doji"])} />);

    expect(await screen.findByLabelText("불러온 계열")).toHaveTextContent(
      "pat_doji",
    );
    expect(requests).toHaveLength(1);
    expect(requests[0].searchParams.get("indicator_key")).toBe("pat_doji");
    expect(requests[0].searchParams.get("feature_time_from")).toBe(CLOSE_TIME);
    expect(requests[0].searchParams.get("feature_time_to")).toBe(CLOSE_TIME);
  });
});

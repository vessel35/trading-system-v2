import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IndicatorDefinition, IndicatorSnapshot } from "../../api/client";
import {
  defaultVisibleSeries,
  PatternGroupDetails,
  SelectedSeriesTruncationNotice,
} from "./chart-tab";
import {
  buildPatternMarkerGroups,
  patternEventDescription,
} from "./pattern-markers";

const OPEN_TIME = "2025-01-01T00:00:00Z";

function patternSnapshot({
  key = "pat_doji@1h",
  strength = 1,
  direction = 1,
  confirmation = false,
  openTime = OPEN_TIME,
}: {
  key?: string;
  strength?: 0.5 | 1;
  direction?: -1 | 1;
  confirmation?: boolean;
  openTime?: string;
} = {}): IndicatorSnapshot {
  return {
    snapshot_seq: 1,
    run_id: "fixture-run",
    indicator_key: key,
    indicator_name: key,
    params_json: {},
    impl_version: "2.0.0+talib.0.7.1",
    pinned_impl: true,
    series_kind: "pattern",
    category: "candlestick",
    impl_note: "TA-Lib fixture",
    min_history: 11,
    computation_mode: "incremental",
    enabled_reason: "all",
    feature_ts: "2025-01-01T01:00:00Z",
    candle_open_time: openTime,
    candle_close_time: "2025-01-01T01:00:00Z",
    value: null,
    value_json: {
      occurred: confirmation ? 0 : 1,
      confirmed: confirmation ? 1 : 0,
      direction,
      strength: confirmation ? 0 : strength,
    },
    is_warmup: false,
  };
}

describe("차트 패턴 표식", () => {
  it("value가 null이어도 성립한 봉에 중립 표식을 만든다", () => {
    const [group] = buildPatternMarkerGroups([patternSnapshot()]);

    expect(group.events).toHaveLength(1);
    expect(group.marker.position).toBe("aboveBar");
    expect(group.marker.shape).toBe("circle");
  });

  it("강도 0.5의 경계 성립과 1.0 성립을 글자와 색으로 구분한다", () => {
    const half = buildPatternMarkerGroups([patternSnapshot({ strength: 0.5 })])[0]
      .marker;
    const full = buildPatternMarkerGroups([patternSnapshot({ strength: 1 })])[0]
      .marker;

    expect(half.text).toContain("경계 0.5");
    expect(full.text).toContain("강도 1.0");
    expect(half.color).not.toBe(full.color);
  });

  it("확인은 성립과 다른 모양으로 표시한다", () => {
    const occurrence = buildPatternMarkerGroups([patternSnapshot()])[0].marker;
    const confirmation = buildPatternMarkerGroups([
      patternSnapshot({ confirmation: true }),
    ])[0].marker;

    expect(occurrence.shape).toBe("circle");
    expect(confirmation.shape).toBe("square");
    expect(confirmation.text).toContain("확인");
    expect(patternEventDescription(
      buildPatternMarkerGroups([patternSnapshot({ confirmation: true })])[0].events[0],
    )).toContain("강도 해당 없음");

    const mixed = buildPatternMarkerGroups([
      patternSnapshot({ key: "pat_doji@1h" }),
      patternSnapshot({ key: "pat_hammer@1h", confirmation: true }),
    ])[0].marker;
    expect(mixed.shape).toBe("square");
    expect(mixed.text).toContain("성립·확인");
  });

  it("TA-Lib 원시 부호를 위치나 화살표 방향으로 쓰지 않는다", () => {
    const positive = buildPatternMarkerGroups([
      patternSnapshot({ direction: 1 }),
    ])[0];
    const negative = buildPatternMarkerGroups([
      patternSnapshot({ direction: -1 }),
    ])[0];

    expect(positive.marker.position).toBe(negative.marker.position);
    expect(positive.marker.shape).toBe(negative.marker.shape);
    expect(positive.marker.color).toBe(negative.marker.color);
    expect(positive.marker.shape).not.toMatch(/arrow/i);
    expect(patternEventDescription(positive.events[0])).toContain(
      "TA-Lib 원시 부호 +1 · 매매 방향 아님",
    );
    expect(patternEventDescription(negative.events[0])).toContain(
      "TA-Lib 원시 부호 -1 · 매매 방향 아님",
    );
  });

  it("같은 봉의 여러 패턴을 개수가 보이는 표식 하나와 상세 목록으로 묶는다", () => {
    const groups = buildPatternMarkerGroups([
      patternSnapshot({ key: "pat_doji@1h" }),
      patternSnapshot({ key: "pat_gravestone_doji@1h" }),
    ]);

    expect(groups).toHaveLength(1);
    expect(groups[0].marker.text).toBe("패턴 2 · 성립");
    render(<PatternGroupDetails group={groups[0]} />);
    expect(screen.getByText("이 봉에서 기록된 패턴 2개")).toBeInTheDocument();
    expect(screen.getByText(/pat_doji@1h \(2\.0\.0\+talib\.0\.7\.1\)/)).toBeInTheDocument();
    expect(
      screen.getByText(/pat_gravestone_doji@1h \(2\.0\.0\+talib\.0\.7\.1\)/),
    ).toBeInTheDocument();
  });

  it("정의 목록의 기본 선택에서 패턴을 모두 끈다", () => {
    const definitions: IndicatorDefinition[] = [
      {
        indicator_key: "EMA(period=9)",
        indicator_name: "EMA",
        series_kind: "indicator",
        impl_version: "1.0.0",
      },
      {
        indicator_key: "pat_doji@1h",
        indicator_name: "pat_doji",
        series_kind: "pattern",
        impl_version: "2.0.0+talib.0.7.1",
      },
    ];

    expect([...defaultVisibleSeries(definitions)]).toEqual(["EMA(period=9)"]);
  });

  it("선택 계열 값이 잘리면 계열 이름과 불완전 사실을 화면에 밝힌다", () => {
    render(
      <SelectedSeriesTruncationNotice
        evidence={{
          rows: [],
          truncated: true,
          truncatedKeys: ["pat_doji@1h"],
          limit: 5_000,
          pageLimit: 25,
        }}
      />,
    );

    const notice = screen.getByRole("status");
    expect(notice).toHaveTextContent("잘렸습니다");
    expect(notice).toHaveTextContent("pat_doji@1h");
    expect(notice).toHaveTextContent("구간 전체가 표시된 것으로 해석하면 안 됩니다");
  });
});

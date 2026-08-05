import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  type CandlestickData,
  type SeriesMarker,
  type UTCTimestamp,
} from "lightweight-charts";
import { AlertTriangle, CandlestickChart, Layers3 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type {
  Candle,
  CandidateEvent,
  Execution,
  IndicatorDefinition,
  IndicatorSnapshot,
  Signal,
} from "../../api/client";
import {
  type IndicatorEvidencePage,
  useChartEvidence,
} from "../../hooks/use-evidence";
import { cn, formatChartTime } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import {
  EvidenceError,
  EvidenceLoading,
  EvidenceTruncationNotice,
} from "./evidence-state";
import {
  buildPatternMarkerGroups,
  type PatternMarkerGroup,
  patternEventDescription,
  seriesLabel,
} from "./pattern-markers";

const INDICATOR_COLORS = ["#2dd4bf", "#38bdf8", "#fbbf24", "#c084fc", "#fb7185"];

// Entries carry a direction and exits carry a reason, and both were previously flattened
// to "진입"/"청산". The marker is the only place a reader sees an individual fill on the
// price chart, so it states which side was opened and how the position actually ended.
const ENTRY_STYLE = {
  LONG: { color: "#34d399", label: "롱 진입" },
  SHORT: { color: "#38bdf8", label: "숏 진입" },
} as const;

const EXIT_STYLE: Record<string, { color: string; label: string }> = {
  TAKE_PROFIT: { color: "#2dd4bf", label: "익절" },
  STOP_LOSS: { color: "#fb7185", label: "손절" },
  TRAILING_STOP: { color: "#fb7185", label: "트레일링 손절" },
  LIQUIDATION: { color: "#ef4444", label: "강제청산" },
  SIGNAL_EXIT: { color: "#94a3b8", label: "신호 청산" },
  REVERSAL: { color: "#c084fc", label: "반대신호 청산" },
  DATA_GAP: { color: "#f59e0b", label: "데이터 공백 청산" },
  END_OF_DATA: { color: "#64748b", label: "기간 종료 청산" },
};

const UNKNOWN_EXIT = { color: "#94a3b8", label: "청산" };

export function entryStyle(positionSide: string): { color: string; label: string } {
  return positionSide === "SHORT" ? ENTRY_STYLE.SHORT : ENTRY_STYLE.LONG;
}

export function exitStyle(exitReason: string | null): { color: string; label: string } {
  if (exitReason === null) return UNKNOWN_EXIT;
  return EXIT_STYLE[exitReason] ?? UNKNOWN_EXIT;
}

const MARKER_LEGEND = [
  { label: "롱 진입", color: ENTRY_STYLE.LONG.color },
  { label: "숏 진입", color: ENTRY_STYLE.SHORT.color },
  { label: "익절", color: EXIT_STYLE.TAKE_PROFIT.color },
  { label: "손절", color: EXIT_STYLE.STOP_LOSS.color },
  { label: "강제청산", color: EXIT_STYLE.LIQUIDATION.color },
  { label: "그 밖의 청산", color: UNKNOWN_EXIT.color },
];

function utcSeconds(value: string): UTCTimestamp {
  return Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
}

function markerTime(
  value: string,
  candles: Candle[],
  belongsToClosedCandle: boolean,
): UTCTimestamp {
  if (candles.length === 0) return utcSeconds(value);
  const first = new Date(candles[0].open_time).getTime();
  const duration =
    new Date(candles[0].close_time).getTime() -
    new Date(candles[0].open_time).getTime();
  const instant = new Date(value).getTime() - (belongsToClosedCandle ? 1 : 0);
  const bucket = Math.max(0, Math.floor((instant - first) / duration));
  return Math.floor((first + bucket * duration) / 1000) as UTCTimestamp;
}

function MarketChart({
  candles,
  indicators,
  executions,
  signals,
  candidates,
  visibleIndicators,
  patternGroups,
  markerVisibility,
  onSelectTrade,
  onSelectPatternGroup,
}: {
  candles: Candle[];
  indicators: IndicatorSnapshot[];
  executions: Execution[];
  signals: Signal[];
  candidates: CandidateEvent[];
  visibleIndicators: Set<string>;
  patternGroups: PatternMarkerGroup[];
  markerVisibility: Record<"trades" | "signals" | "candidates", boolean>;
  onSelectTrade: (tradeId: number) => void;
  onSelectPatternGroup: (groupId: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current || candles.length === 0) return;
    const element = container.current;
    const chart = createChart(element, {
      width: element.clientWidth,
      height: 560,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      timeScale: {
        borderColor: "rgba(148,163,184,0.18)",
        timeVisible: true,
        tickMarkFormatter: (time: number) => formatChartTime(time),
      },
      localization: {
        timeFormatter: (time: number) => formatChartTime(time),
      },
      rightPriceScale: {
        borderColor: "rgba(148,163,184,0.18)",
        scaleMargins: { top: 0.05, bottom: 0.28 },
      },
    });
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#2dd4bf",
      downColor: "#fb7185",
      wickUpColor: "#5eead4",
      wickDownColor: "#fda4af",
      borderVisible: false,
    });
    const candleData: CandlestickData<UTCTimestamp>[] = candles.map((candle) => ({
      time: utcSeconds(candle.open_time),
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));
    candleSeries.setData(candleData);

    const grouped = new Map<string, IndicatorSnapshot[]>();
    indicators.forEach((snapshot) => {
      if (
        snapshot.series_kind !== "indicator" ||
        !visibleIndicators.has(snapshot.indicator_key) ||
        snapshot.value === null
      ) {
        return;
      }
      const rows = grouped.get(snapshot.indicator_key) ?? [];
      rows.push(snapshot);
      grouped.set(snapshot.indicator_key, rows);
    });
    [...grouped].forEach(([key, rows], index) => {
      const auxiliary = rows[0]?.indicator_name.toUpperCase() === "ATR";
      const series = chart.addSeries(LineSeries, {
        color: INDICATOR_COLORS[index % INDICATOR_COLORS.length],
        lineWidth: auxiliary ? 1 : 2,
        priceScaleId: auxiliary ? "atr-pane" : "right",
        title: seriesLabel(key, rows[0].impl_version),
      });
      if (auxiliary) {
        chart.priceScale("atr-pane").applyOptions({
          scaleMargins: { top: 0.78, bottom: 0.02 },
          borderVisible: false,
        });
      }
      series.setData(
        rows.map((row) => ({
          time: markerTime(row.feature_ts, candles, true),
          value: row.value!,
        })),
      );
    });

    const markers: SeriesMarker<UTCTimestamp>[] = [];
    patternGroups.forEach((group) => markers.push(group.marker));
    if (markerVisibility.trades) {
      executions.forEach((execution) => {
        const isExit = execution.exit_reason !== null || execution.reduce_only;
        const style = isExit
          ? exitStyle(execution.exit_reason)
          : entryStyle(execution.position_side);
        markers.push({
          id: execution.trade_id ? `trade:${execution.trade_id}` : undefined,
          time: markerTime(execution.execution_ts, candles, false),
          position: isExit ? "aboveBar" : "belowBar",
          color: style.color,
          shape: isExit ? "arrowDown" : "arrowUp",
          text: execution.trade_id
            ? `${style.label} #${execution.trade_id}`
            : `${style.label} ${execution.side}`,
        });
      });
    }
    if (markerVisibility.signals) {
      signals.forEach((signal) => {
        markers.push({
          id: `signal:${signal.signal_id}`,
          time: markerTime(signal.decision_ts, candles, true),
          position: signal.derived_side === "SHORT" ? "aboveBar" : "belowBar",
          color: signal.is_warmup ? "rgba(192,132,252,0.4)" : "#c084fc",
          shape: "circle",
          text: `S${signal.signal_id}`,
        });
      });
    }
    if (markerVisibility.candidates) {
      candidates.forEach((candidate) => {
        markers.push({
          id: candidate.linked_trade_id
            ? `trade:${candidate.linked_trade_id}`
            : `candidate:${candidate.candidate_id}`,
          time: markerTime(candidate.ts, candles, true),
          position: candidate.would_be_side === "SHORT" ? "aboveBar" : "belowBar",
          color: candidate.blocked_by ? "#f59e0b" : "#64748b",
          shape: "square",
          text: candidate.blocked_by
            ? `차단:${candidate.blocked_by}`
            : `C${candidate.candidate_id}`,
        });
      });
    }
    markers.sort((left, right) => Number(left.time) - Number(right.time));
    createSeriesMarkers(candleSeries, markers);
    chart.subscribeClick((parameter) => {
      const markerId = parameter.hoveredInfo?.objectId ?? parameter.hoveredObjectId;
      if (typeof markerId !== "string") return;
      if (markerId.startsWith("pattern:")) {
        onSelectPatternGroup(markerId);
        return;
      }
      if (!markerId.startsWith("trade:")) return;
      const tradeId = Number(markerId.slice("trade:".length));
      if (Number.isInteger(tradeId) && tradeId > 0) onSelectTrade(tradeId);
    });
    chart.timeScale().fitContent();
    const resize = new ResizeObserver(() =>
      chart.applyOptions({ width: element.clientWidth }),
    );
    resize.observe(element);
    return () => {
      resize.disconnect();
      chart.remove();
    };
  }, [
    candidates,
    candles,
    executions,
    indicators,
    markerVisibility,
    onSelectTrade,
    onSelectPatternGroup,
    patternGroups,
    signals,
    visibleIndicators,
  ]);

  return <div ref={container} className="h-[560px] w-full" aria-label="시장 캔들 차트" />;
}

export function SelectedSeriesTruncationNotice({
  evidence,
}: {
  evidence: IndicatorEvidencePage | undefined;
}) {
  if (!evidence?.truncated) return null;
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-sm text-amber-100"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        선택 계열 값 일부가 Evidence 안전 상한에 걸려 잘렸습니다. 잘린 계열은
        {" "}
        <span className="font-mono">{evidence.truncatedKeys.join(", ")}</span>
        이며, 현재 구간 전체가 표시된 것으로 해석하면 안 됩니다.
      </p>
    </div>
  );
}

export function defaultVisibleSeries(
  definitions: IndicatorDefinition[],
): Set<string> {
  return new Set(
    definitions
      .filter((definition) => definition.series_kind === "indicator")
      .map((definition) => definition.indicator_key),
  );
}

export function PatternGroupDetails({ group }: { group: PatternMarkerGroup }) {
  return (
    <div
      className="mt-4 rounded-lg border border-violet-500/25 bg-violet-500/[0.08] p-4"
      aria-label="선택한 봉의 패턴 목록"
    >
      <p className="text-sm font-medium">
        이 봉에서 기록된 패턴 {group.events.length}개
      </p>
      <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
        {group.events.map((event) => (
          <li key={`${event.key}:${event.kind}`}>
            {patternEventDescription(event)}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ChartTab({
  runId,
  onSelectTrade,
}: {
  runId: string;
  onSelectTrade: (tradeId: number) => void;
}) {
  const [visibleIndicators, setVisibleIndicators] = useState<Set<string> | null>(null);
  const evidence = useChartEvidence(runId, visibleIndicators);
  const indicators = evidence.indicators.data ?? [];
  const definitions = evidence.definitions.data ?? [];
  const indicatorDefinitions = useMemo(
    () => definitions.filter((item) => item.series_kind === "indicator"),
    [definitions],
  );
  const patternDefinitions = useMemo(
    () => definitions.filter((item) => item.series_kind === "pattern"),
    [definitions],
  );
  const effectiveIndicators =
    visibleIndicators ?? defaultVisibleSeries(definitions);
  const patternGroups = useMemo(
    () => buildPatternMarkerGroups(indicators),
    [indicators],
  );
  const [selectedPatternGroupId, setSelectedPatternGroupId] = useState<string | null>(
    null,
  );
  const selectedPatternGroup = patternGroups.find(
    (group) => group.id === selectedPatternGroupId,
  );
  const [markerVisibility, setMarkerVisibility] = useState({
    trades: true,
    signals: false,
    candidates: false,
  });

  if (
    evidence.candles.isLoading ||
    evidence.definitions.isLoading ||
    evidence.indicators.isLoading ||
    evidence.signals.isLoading ||
    evidence.candidates.isLoading ||
    evidence.executions.isLoading
  ) {
    return <EvidenceLoading />;
  }
  const error =
    evidence.candles.error ??
    evidence.definitions.error ??
    evidence.indicators.error ??
    evidence.signals.error ??
    evidence.candidates.error ??
    evidence.executions.error;
  if (error) return <EvidenceError error={error} />;
  const candles = evidence.candles.data?.data ?? [];

  return (
    <div className="space-y-4">
      <EvidenceTruncationNotice
        sources={[
          evidence.signals.evidence,
          evidence.candidates.evidence,
          evidence.executions.evidence,
        ]}
      />
      <SelectedSeriesTruncationNotice evidence={evidence.indicators.evidence} />
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <CandlestickChart className="h-4 w-4 text-teal-400" />
                시장 구조 · 캔들 + 저장 계열
              </CardTitle>
              <CardDescription>
                crypto_data 1m → {evidence.candles.data?.page.timeframe} 확정봉{" "}
                {candles.length.toLocaleString()} /{" "}
                {evidence.candles.data?.page.total.toLocaleString()}개 · 지표 재계산 없음
              </CardDescription>
            </div>
            <Badge variant="outline">KST · READ ONLY</Badge>
          </div>
          <div
            className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
            aria-label="거래 마커 범례"
          >
            <span className="font-medium text-foreground">마커</span>
            {MARKER_LEGEND.map((item) => (
              <span key={item.label} className="flex items-center gap-1">
                <span
                  aria-hidden
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                {item.label}
              </span>
            ))}
            <span>▲ 진입 · ▼ 청산</span>
          </div>
          <div className="mt-3 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-xs font-medium text-muted-foreground">지표</span>
              {indicatorDefinitions.map((definition) => (
                <Button
                  key={definition.indicator_key}
                  size="sm"
                  variant={
                    effectiveIndicators.has(definition.indicator_key)
                      ? "secondary"
                      : "outline"
                  }
                  onClick={() => {
                    const next = new Set(effectiveIndicators);
                    if (next.has(definition.indicator_key)) {
                      next.delete(definition.indicator_key);
                    } else {
                      next.add(definition.indicator_key);
                    }
                    setVisibleIndicators(next);
                  }}
                >
                  <Layers3 className="mr-1.5 h-3.5 w-3.5" />
                  {seriesLabel(definition.indicator_key, definition.impl_version)}
                </Button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-xs font-medium text-muted-foreground">패턴</span>
              {patternDefinitions.map((definition) => (
                <Button
                  key={definition.indicator_key}
                  size="sm"
                  variant={
                    effectiveIndicators.has(definition.indicator_key)
                      ? "secondary"
                      : "outline"
                  }
                  onClick={() => {
                    const next = new Set(effectiveIndicators);
                    if (next.has(definition.indicator_key)) {
                      next.delete(definition.indicator_key);
                    } else {
                      next.add(definition.indicator_key);
                    }
                    setVisibleIndicators(next);
                  }}
                >
                  <CandlestickChart className="mr-1.5 h-3.5 w-3.5" />
                  {seriesLabel(definition.indicator_key, definition.impl_version)}
                </Button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {(["trades", "signals", "candidates"] as const).map((kind) => (
                <Button
                  key={kind}
                  size="sm"
                  variant={markerVisibility[kind] ? "secondary" : "outline"}
                  onClick={() =>
                    setMarkerVisibility((current) => ({
                      ...current,
                      [kind]: !current[kind],
                    }))
                  }
                  className={cn(kind === "trades" && "ml-2")}
                >
                  {kind === "trades"
                    ? "진입/청산"
                    : kind === "signals"
                      ? "신호"
                      : "후보"}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {evidence.candles.data?.page.truncated && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-sm text-amber-100">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                차트 표시 상한 {evidence.candles.data.page.limit.toLocaleString()}봉으로
                앞부분만 표시 중입니다. 전체{" "}
                {evidence.candles.data.page.total.toLocaleString()}봉이며, 전체 구간을
                보려면 API 조회 기간을 좁혀 확인하세요.
              </p>
            </div>
          )}
          {candles.length > 0 ? (
            <MarketChart
              candles={candles}
              indicators={indicators}
              executions={evidence.executions.data ?? []}
              signals={evidence.signals.data ?? []}
              candidates={evidence.candidates.data ?? []}
              visibleIndicators={effectiveIndicators}
              patternGroups={patternGroups}
              markerVisibility={markerVisibility}
              onSelectTrade={onSelectTrade}
              onSelectPatternGroup={setSelectedPatternGroupId}
            />
          ) : (
            <div className="grid min-h-80 place-items-center text-sm text-muted-foreground">
              이 범위에 완성된 캔들이 없습니다.
            </div>
          )}
          {selectedPatternGroup && <PatternGroupDetails group={selectedPatternGroup} />}
        </CardContent>
      </Card>
      <p className="text-center text-[10px] text-muted-foreground">
        ATR은 하단 동기 가격척도 · 패턴 표식은 봉 위의 중립 사건이며 원시 부호는 매매 방향이
        아님 · 묶음 표식을 누르면 상세 목록
      </p>
    </div>
  );
}

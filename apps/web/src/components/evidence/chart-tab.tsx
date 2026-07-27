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
  IndicatorSnapshot,
  Signal,
} from "../../api/client";
import { useChartEvidence } from "../../hooks/use-evidence";
import { cn } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import {
  EvidenceError,
  EvidenceLoading,
  EvidenceTruncationNotice,
} from "./evidence-state";

const INDICATOR_COLORS = ["#2dd4bf", "#38bdf8", "#fbbf24", "#c084fc", "#fb7185"];

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
  markerVisibility,
  onSelectTrade,
}: {
  candles: Candle[];
  indicators: IndicatorSnapshot[];
  executions: Execution[];
  signals: Signal[];
  candidates: CandidateEvent[];
  visibleIndicators: Set<string>;
  markerVisibility: Record<"trades" | "signals" | "candidates", boolean>;
  onSelectTrade: (tradeId: number) => void;
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
      if (!visibleIndicators.has(snapshot.indicator_key) || snapshot.value === null) return;
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
        title: key,
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
    if (markerVisibility.trades) {
      executions.forEach((execution) => {
        const isExit = execution.exit_reason !== null || execution.reduce_only;
        markers.push({
          id: execution.trade_id ? `trade:${execution.trade_id}` : undefined,
          time: markerTime(execution.execution_ts, candles, false),
          position: isExit ? "aboveBar" : "belowBar",
          color: execution.exit_reason === "LIQUIDATION" ? "#ef4444" : isExit ? "#fb7185" : "#34d399",
          shape: isExit ? "arrowDown" : "arrowUp",
          text: execution.trade_id
            ? `${isExit ? "청산" : "진입"} #${execution.trade_id}`
            : execution.side,
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
      if (typeof markerId !== "string" || !markerId.startsWith("trade:")) return;
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
    signals,
    visibleIndicators,
  ]);

  return <div ref={container} className="h-[560px] w-full" aria-label="시장 캔들 차트" />;
}

export function ChartTab({
  runId,
  onSelectTrade,
}: {
  runId: string;
  onSelectTrade: (tradeId: number) => void;
}) {
  const evidence = useChartEvidence(runId);
  const indicators = evidence.indicators.data ?? [];
  const indicatorKeys = useMemo(
    () => [...new Set(indicators.map((item) => item.indicator_key))],
    [indicators],
  );
  const [visibleIndicators, setVisibleIndicators] = useState<Set<string> | null>(null);
  const effectiveIndicators = visibleIndicators ?? new Set(indicatorKeys);
  const [markerVisibility, setMarkerVisibility] = useState({
    trades: true,
    signals: false,
    candidates: false,
  });

  if (
    evidence.candles.isLoading ||
    evidence.indicators.isLoading ||
    evidence.signals.isLoading ||
    evidence.candidates.isLoading ||
    evidence.executions.isLoading
  ) {
    return <EvidenceLoading />;
  }
  const error =
    evidence.candles.error ??
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
          evidence.indicators.evidence,
          evidence.signals.evidence,
          evidence.candidates.evidence,
          evidence.executions.evidence,
        ]}
      />
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <CandlestickChart className="h-4 w-4 text-teal-400" />
                시장 구조 · 캔들 + 저장 지표
              </CardTitle>
              <CardDescription>
                crypto_data 1m → {evidence.candles.data?.page.timeframe} 확정봉{" "}
                {candles.length.toLocaleString()} /{" "}
                {evidence.candles.data?.page.total.toLocaleString()}개 · 지표 재계산 없음
              </CardDescription>
            </div>
            <Badge variant="outline">UTC · READ ONLY</Badge>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {indicatorKeys.map((key) => (
              <Button
                key={key}
                size="sm"
                variant={effectiveIndicators.has(key) ? "secondary" : "outline"}
                onClick={() => {
                  const next = new Set(effectiveIndicators);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  setVisibleIndicators(next);
                }}
              >
                <Layers3 className="mr-1.5 h-3.5 w-3.5" />
                {key}
              </Button>
            ))}
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
                {kind === "trades" ? "진입/청산" : kind === "signals" ? "신호" : "후보"}
              </Button>
            ))}
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
              markerVisibility={markerVisibility}
              onSelectTrade={onSelectTrade}
            />
          ) : (
            <div className="grid min-h-80 place-items-center text-sm text-muted-foreground">
              이 범위에 완성된 캔들이 없습니다.
            </div>
          )}
        </CardContent>
      </Card>
      <p className="text-center text-[10px] text-muted-foreground">
        ATR은 하단 동기 가격척도 · 매매/실현 후보 마커 클릭 시 거래 드로어
      </p>
    </div>
  );
}

import { useQueries, useQuery } from "@tanstack/react-query";
import {
  ColorType,
  createChart,
  LineSeries,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  AlertTriangle,
  ArrowLeft,
  GitCompareArrows,
  RefreshCcw,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "wouter";

import {
  apiClient,
  apiRequestError,
  type ChartSummary,
  type EquityPoint,
  type RunComparisonItem,
} from "../api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { useComparisonBasket } from "../contexts/comparison-basket";
import { allPages } from "../hooks/use-evidence";
import {
  cn,
  formatDecimalString,
  formatMetric,
  shortHash,
} from "../lib/utils";

const SERIES_COLORS = [
  "#94a3b8",
  "#2dd4bf",
  "#38bdf8",
  "#fb7185",
  "#fbbf24",
  "#c084fc",
  "#34d399",
  "#f97316",
];

type EquityDatum = { time: UTCTimestamp; value: number };

type MetricDefinition = {
  key: keyof NonNullable<RunComparisonItem["summary"]>;
  label: string;
  lowerIsBetter?: boolean;
  percent?: boolean;
};

const METRICS: MetricDefinition[] = [
  { key: "pf", label: "PF" },
  { key: "sortino", label: "Sortino" },
  { key: "calmar_or_mar", label: "Calmar / MAR" },
  { key: "sqn", label: "SQN" },
  { key: "mdd", label: "MDD", lowerIsBetter: true, percent: true },
  { key: "ror", label: "Risk of ruin", lowerIsBetter: true, percent: true },
  { key: "ulcer", label: "Ulcer", lowerIsBetter: true },
  { key: "win_rate", label: "Win rate", percent: true },
  { key: "psr", label: "PSR" },
];

function flattenSettings(item: RunComparisonItem): Record<string, string> {
  const base: Record<string, string> = {
    symbol: item.run.symbol,
    timeframe: item.run.timeframe,
    exchange: item.run.exchange,
    market_type: item.run.market_type,
    data_source: item.run.data_source,
    period_start: item.run.period_start,
    period_end: item.run.period_end,
    sizing_method: item.run.sizing_method,
    risk_per_trade: item.run.risk_per_trade ?? "—",
    position_size_pct: item.run.position_size_pct ?? "—",
    seed: String(item.run.seed),
    config_hash: item.run.config_hash,
    source_data_hash: item.run.source_data_hash ?? "—",
  };
  if (
    typeof item.run.params_json === "object" &&
    item.run.params_json !== null &&
    !Array.isArray(item.run.params_json)
  ) {
    Object.entries(item.run.params_json)
      .sort(([left], [right]) => left.localeCompare(right))
      .forEach(([key, value]) => {
        base[`params.${key}`] =
          typeof value === "string" ? value : JSON.stringify(value);
      });
  }
  return base;
}

async function fetchEquity(runId: string): Promise<EquityDatum[]> {
  const chart = await allPages<ChartSummary>(async (after_seq) => {
    const { data, error } = await apiClient.GET(
      "/api/v1/runs/{run_id}/chart-summaries",
      {
        params: {
          path: { run_id: runId },
          query: { after_seq, limit: 200, series_name: "equity" },
        },
      },
    );
    if (error) throw apiRequestError(error);
    if (!data) throw new Error("자본곡선 요약 응답이 비어 있습니다.");
    return data;
  });
  if (chart.rows.some((point) => point.value !== null)) {
    return chart.rows.flatMap((point) =>
      point.value === null
        ? []
        : [
            {
              time: Math.floor(new Date(point.bucket_ts).getTime() / 1000) as UTCTimestamp,
              value: point.value,
            },
          ],
    );
  }
  const equity = await allPages<EquityPoint>(async (after_seq) => {
    const { data, error } = await apiClient.GET("/api/v1/runs/{run_id}/equity", {
      params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
    });
    if (error) throw apiRequestError(error);
    if (!data) throw new Error("자본 Evidence 응답이 비어 있습니다.");
    return data;
  });
  return equity.rows.map((point) => ({
    time: Math.floor(new Date(point.ts).getTime() / 1000) as UTCTimestamp,
    value: Number(point.total_equity),
  }));
}

function EquityOverlap({
  runs,
  series,
}: {
  runs: RunComparisonItem[];
  series: Array<EquityDatum[] | undefined>;
}) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !series.some((points) => points?.length)) return;
    const element = container.current;
    const chart = createChart(element, {
      width: element.clientWidth,
      height: 340,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      timeScale: { borderColor: "rgba(148,163,184,0.18)", timeVisible: true },
      rightPriceScale: { borderColor: "rgba(148,163,184,0.18)" },
    });
    series.forEach((points, index) => {
      if (!points?.length) return;
      const line = chart.addSeries(LineSeries, {
        color: SERIES_COLORS[index % SERIES_COLORS.length],
        lineWidth: index === 0 ? 3 : 2,
        title: runs[index].run.run_name,
      });
      line.setData(points);
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
  }, [runs, series]);
  return <div ref={container} className="h-[340px] w-full" aria-label="실행 자본곡선 비교" />;
}

function metricNumber(
  item: RunComparisonItem,
  metric: MetricDefinition,
): number | null {
  const value = item.summary?.[metric.key];
  return typeof value === "number" ? value : null;
}

export function ComparisonPage() {
  const [, navigate] = useLocation();
  const basket = useComparisonBasket();
  const runIds = basket.items.map((item) => item.run_id);
  const comparison = useQuery({
    queryKey: ["comparison", ...runIds],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/runs:compare", {
        params: { query: { run_ids: runIds } },
      });
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("실행 비교 응답이 비어 있습니다.");
      return data;
    },
    enabled: runIds.length >= 2,
  });
  const runs = comparison.data?.data ?? [];
  const [baselineId, setBaselineId] = useState("");
  const [diffOnly, setDiffOnly] = useState(true);
  const [metricOnly, setMetricOnly] = useState(false);
  const effectiveBaselineId =
    runs.some((item) => item.run.run_id === baselineId)
      ? baselineId
      : (runs[0]?.run.run_id ?? "");
  const baselineIndex = Math.max(
    0,
    runs.findIndex((item) => item.run.run_id === effectiveBaselineId),
  );
  const baseline = runs[baselineIndex];
  const settings = useMemo(() => runs.map(flattenSettings), [runs]);
  const settingKeys = useMemo(() => {
    const keys = [...new Set(settings.flatMap((item) => Object.keys(item)))];
    return diffOnly
      ? keys.filter((key) => new Set(settings.map((item) => item[key] ?? "—")).size > 1)
      : keys;
  }, [diffOnly, settings]);
  const axes = new Set(runs.map((item) => `${item.run.symbol}|${item.run.timeframe}`));
  const evaluationWindows = new Set(
    runs.map((item) => `${item.run.period_start}|${item.run.period_end}`),
  );
  const sameRerunIds = new Set(
    baseline
      ? runs
          .filter(
            (item) =>
              item.run.run_id !== baseline.run.run_id &&
              item.run.config_hash === baseline.run.config_hash &&
              item.run.source_data_hash === baseline.run.source_data_hash,
          )
          .map((item) => item.run.run_id)
      : [],
  );
  const equityQueries = useQueries({
    queries: runs.map((item) => ({
      queryKey: ["comparison", item.run.run_id, "equity"],
      queryFn: () => fetchEquity(item.run.run_id),
      staleTime: 60_000,
    })),
  });

  if (basket.items.length < 2) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Button variant="ghost" size="sm" onClick={() => navigate("/runs")}>
          <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
          카탈로그
        </Button>
        <Card className="mt-4">
          <CardContent className="grid min-h-80 place-items-center text-center">
            <div>
              <GitCompareArrows className="mx-auto h-10 w-10 text-muted-foreground" />
              <p className="mt-4 font-medium">비교할 실행을 두 개 이상 담으세요.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                현재 바스켓 {basket.items.length}개 · 카탈로그 체크박스로 추가
              </p>
              <Button className="mt-4" onClick={() => navigate("/runs")}>
                실행 고르기
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (comparison.isLoading) {
    return (
      <div className="mx-auto max-w-[1500px] space-y-4 p-6">
        <Skeleton className="h-28" />
        <Skeleton className="h-96" />
        <Skeleton className="h-80" />
      </div>
    );
  }
  if (comparison.isError) {
    return (
      <div className="grid min-h-[70vh] place-items-center p-6 text-center">
        <div>
          <AlertTriangle className="mx-auto h-8 w-8 text-red-400" />
          <p className="mt-3 font-medium">실행 비교를 불러오지 못했습니다.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {comparison.error.message}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/runs")}>
          <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
          카탈로그
        </Button>
        <Badge variant="outline">저장 요약 · 재계산 없음</Badge>
      </div>

      <Card className="shadow-glow">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-xl">
                <GitCompareArrows className="h-5 w-5 text-teal-400" />
                실행 비교 ({runs.length})
              </CardTitle>
              <CardDescription>
                기준선을 고정해 설정 diff와 저장 지표 델타를 대조합니다.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                value={effectiveBaselineId}
                onChange={(event) => setBaselineId(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-xs"
                aria-label="비교 기준선"
              >
                {runs.map((item) => (
                  <option key={item.run.run_id} value={item.run.run_id}>
                    기준: {item.run.run_name}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                variant={diffOnly ? "secondary" : "outline"}
                onClick={() => setDiffOnly((value) => !value)}
              >
                설정 diff만
              </Button>
              <Button
                size="sm"
                variant={metricOnly ? "secondary" : "outline"}
                onClick={() => setMetricOnly((value) => !value)}
              >
                지표만
              </Button>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {runs.map((item, index) => (
              <Badge
                key={item.run.run_id}
                variant={index === baselineIndex ? "success" : "secondary"}
                className="gap-1.5"
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: SERIES_COLORS[index % SERIES_COLORS.length] }}
                />
                {item.run.run_name}
                {sameRerunIds.has(item.run.run_id) && (
                  <RefreshCcw className="h-3 w-3" />
                )}
              </Badge>
            ))}
          </div>
        </CardHeader>
      </Card>

      {(axes.size > 1 || evaluationWindows.size > 1) && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-sm text-amber-100">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {axes.size > 1
            ? "서로 다른 symbol/timeframe 축이 섞였습니다. "
            : ""}
          {evaluationWindows.size > 1
            ? "평가 구간(period_start/period_end)이 서로 다릅니다. "
            : ""}
          설정 diff와 자본곡선 시간 범위를 함께 확인하세요.
        </div>
      )}
      {sameRerunIds.size > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-sky-500/25 bg-sky-500/10 p-3 text-sm text-sky-100">
          <RefreshCcw className="h-4 w-4 shrink-0" />
          config_hash와 source_data_hash가 같은 실행은 “같은 설정 재실행”입니다. 결과가 다르면
          결정성을 점검하세요.
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>설정 diff + 지표 델타</CardTitle>
          <CardDescription>
            녹색은 기준선 대비 개선 · MDD/RoR/Ulcer는 낮을수록 좋아 색 방향 반전
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[900px] border-collapse text-xs">
            <thead>
              <tr className="border-b">
                <th className="sticky left-0 z-10 bg-card p-3 text-left text-muted-foreground">
                  항목
                </th>
                {runs.map((item, index) => (
                  <th key={item.run.run_id} className="min-w-52 p-3 text-left">
                    <p className="font-medium">{item.run.run_name}</p>
                    <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                      {shortHash(item.run.run_id, 18)}
                    </p>
                    {index === baselineIndex && (
                      <Badge variant="success" className="mt-2">
                        기준선
                      </Badge>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!metricOnly &&
                settingKeys.map((key) => (
                  <tr key={key} className="border-b">
                    <td className="sticky left-0 z-10 bg-card p-3 font-medium">{key}</td>
                    {runs.map((item, index) => {
                      const value = settings[index][key] ?? "—";
                      const changed = value !== (settings[baselineIndex]?.[key] ?? "—");
                      return (
                        <td
                          key={item.run.run_id}
                          className={cn("p-3 font-mono", changed && "bg-amber-500/[0.08]")}
                          title={value}
                        >
                          {key.includes("hash") ? shortHash(value, 16) : value}
                          {changed && <Badge className="ml-2">변경</Badge>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              {METRICS.map((metric) => {
                const baselineValue = baseline ? metricNumber(baseline, metric) : null;
                return (
                  <tr key={String(metric.key)} className="border-b bg-muted/[0.08]">
                    <td className="sticky left-0 z-10 bg-card p-3 font-medium">
                      {metric.label}
                      {metric.lowerIsBetter && (
                        <span className="ml-1 text-[9px] text-muted-foreground">↓ good</span>
                      )}
                    </td>
                    {runs.map((item, index) => {
                      const value = metricNumber(item, metric);
                      const delta =
                        value !== null && baselineValue !== null ? value - baselineValue : null;
                      const improved =
                        delta !== null &&
                        delta !== 0 &&
                        (metric.lowerIsBetter ? delta < 0 : delta > 0);
                      return (
                        <td key={item.run.run_id} className="p-3">
                          <span className="tabular font-semibold">
                            {formatMetric(value, {
                              style: metric.percent ? "percent" : "decimal",
                              maximumFractionDigits: metric.percent ? 2 : 3,
                            })}
                          </span>
                          {index !== baselineIndex && delta !== null && (
                            <span
                              className={cn(
                                "tabular ml-2",
                                delta === 0
                                  ? "text-muted-foreground"
                                  : improved
                                    ? "text-emerald-400"
                                    : "text-red-400",
                              )}
                            >
                              ({delta > 0 ? "+" : ""}
                              {metric.percent
                                ? `${(delta * 100).toFixed(2)}pp`
                                : delta.toFixed(3)}
                              )
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              <tr className="border-b">
                <td className="sticky left-0 z-10 bg-card p-3 font-medium">Net PnL</td>
                {runs.map((item) => (
                  <td key={item.run.run_id} className="tabular p-3">
                    {formatDecimalString(item.summary?.net_pnl_total ?? null)}
                    <span className="ml-2 text-[9px] text-muted-foreground">
                      문자열 표시
                    </span>
                  </td>
                ))}
              </tr>
              <tr>
                <td className="sticky left-0 z-10 bg-card p-3 font-medium">gate / route</td>
                {runs.map((item) => (
                  <td key={item.run.run_id} className="p-3">
                    <Badge variant="outline">{item.summary?.gate_verdict ?? "—"}</Badge>
                    <span className="ml-2">{item.summary?.decision_route ?? "—"}</span>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>자본곡선 겹침</CardTitle>
              <CardDescription>
                CHART_SUMMARY 우선 · 없으면 PORTFOLIO_PNL · run별 고정 색
              </CardDescription>
            </div>
            {equityQueries.some((query) => query.isError) && (
              <Badge variant="warning">일부 Evidence unavailable</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {equityQueries.some((query) => query.isLoading) ? (
            <Skeleton className="h-[340px]" />
          ) : (
            <EquityOverlap runs={runs} series={equityQueries.map((query) => query.data)} />
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap justify-center gap-2">
        {basket.items.map((item) => (
          <Button
            key={item.run_id}
            variant="ghost"
            size="sm"
            onClick={() => basket.remove(item.run_id)}
          >
            <X className="mr-1 h-3 w-3" />
            {item.run_name}
          </Button>
        ))}
      </div>
    </div>
  );
}

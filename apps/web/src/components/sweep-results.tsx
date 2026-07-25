import {
  AlertTriangle,
  Check,
  GitCompareArrows,
  Grid3X3,
  List,
  LoaderCircle,
  Maximize2,
} from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import { useLocation } from "wouter";

import type { RunComparisonItem } from "../api/client";
import type { TrackedSweep } from "../contexts/run-jobs";
import { useComparisonBasket } from "../contexts/comparison-basket";
import { useSweep } from "../hooks/use-p2b";
import { cn, formatMetric, shortHash } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";

type MetricName = "sortino" | "pf" | "sqn" | "mdd" | "win_rate";

const metrics: MetricName[] = ["sortino", "pf", "sqn", "mdd", "win_rate"];

function metricValue(item: RunComparisonItem, metric: MetricName): number | null {
  return item.summary?.[metric] ?? null;
}

function variedParameters(runs: RunComparisonItem[]): string[] {
  const keys = new Set(runs.flatMap((item) => Object.keys(item.run.params_json ?? {})));
  return [...keys].filter((key) => {
    const values = runs.map((item) =>
      JSON.stringify((item.run.params_json as Record<string, unknown>)[key]),
    );
    return new Set(values).size > 1;
  });
}

function parameterValue(item: RunComparisonItem, key: string): string {
  const value = (item.run.params_json as Record<string, unknown>)[key];
  return typeof value === "string" ? value : JSON.stringify(value);
}

function SweepCell({
  item,
  metric,
  best,
  selected,
  onSelect,
}: {
  item: RunComparisonItem | undefined;
  metric: MetricName;
  best: number | null;
  selected: boolean;
  onSelect: () => void;
}) {
  if (!item) return <div className="min-h-16 rounded-md border border-dashed" />;
  const value = metricValue(item, metric);
  const isBest = value !== null && value === best;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "relative min-h-16 rounded-md border p-2 text-left transition-colors",
        value === null
          ? "bg-muted/30 text-muted-foreground"
          : "border-teal-500/20 bg-teal-500/10 hover:bg-teal-500/20",
        selected && "ring-2 ring-teal-400",
        isBest && "border-emerald-400/60 bg-emerald-500/15",
      )}
    >
      {isBest && (
        <Badge variant="success" className="absolute right-1 top-1 px-1.5 py-0 text-[9px]">
          BEST
        </Badge>
      )}
      <span className="tabular block pt-3 text-sm font-semibold">
        {formatMetric(value, {
          style: metric === "mdd" || metric === "win_rate" ? "percent" : "decimal",
        })}
      </span>
      <span className="mt-1 block font-mono text-[9px] text-muted-foreground">
        {shortHash(item.run.run_id, 12)}
      </span>
    </button>
  );
}

export function SweepResults({ sweep }: { sweep: TrackedSweep | undefined }) {
  const [, navigate] = useLocation();
  const basket = useComparisonBasket();
  const result = useSweep(
    sweep?.status.status === "SUCCEEDED" ? sweep.status.sweep_id : null,
  );
  const [metric, setMetric] = useState<MetricName>("sortino");
  const [view, setView] = useState<"heatmap" | "list">("heatmap");
  const [selected, setSelected] = useState<string[]>([]);

  const axes = useMemo(
    () => variedParameters(result.data?.runs ?? []).slice(0, 2),
    [result.data?.runs],
  );
  const xAxis = axes[0] ?? "run";
  const yAxis = axes[1] ?? null;
  const xValues = useMemo(
    () =>
      xAxis === "run"
        ? (result.data?.runs ?? []).map((item) => item.run.run_name)
        : [
            ...new Set(
              (result.data?.runs ?? []).map((item) => parameterValue(item, xAxis)),
            ),
          ],
    [result.data?.runs, xAxis],
  );
  const yValues = useMemo(
    () =>
      yAxis
        ? [
            ...new Set(
              (result.data?.runs ?? []).map((item) => parameterValue(item, yAxis)),
            ),
          ]
        : ["all"],
    [result.data?.runs, yAxis],
  );
  const values = (result.data?.runs ?? [])
    .map((item) => metricValue(item, metric))
    .filter((value): value is number => value !== null);
  const lowerIsBetter = metric === "mdd";
  const best =
    values.length === 0
      ? null
      : lowerIsBetter
        ? Math.min(...values)
        : Math.max(...values);
  const selectedItems = (result.data?.runs ?? []).filter((item) =>
    selected.includes(item.run.run_id),
  );

  if (!sweep) return null;

  if (sweep.status.status !== "SUCCEEDED") {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 p-5">
          {sweep.status.status === "FAILED" ? (
            <AlertTriangle className="h-5 w-5 text-red-400" />
          ) : (
            <LoaderCircle className="h-5 w-5 animate-spin text-teal-300" />
          )}
          <div>
            <p className="text-sm font-medium">스윕 {sweep.status.status}</p>
            <p className="text-xs text-muted-foreground">
              {sweep.status.error?.message ??
                "동일한 단일 dry-run 워커에서 셀을 직렬 실행하고 있습니다."}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (result.isLoading || !result.data) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 p-5 text-xs">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          저장된 스윕 결과를 불러오는 중입니다.
        </CardContent>
      </Card>
    );
  }

  if (result.isError) {
    return (
      <Card>
        <CardContent className="p-5 text-xs text-red-300">
          {result.error.message}
        </CardContent>
      </Card>
    );
  }

  const aggregateRisk =
    result.data.oos_degradation !== null && result.data.oos_degradation >= 0.5
      ? "OOS 성능 저하가 저장 임계 50% 이상입니다."
      : result.data.psr !== null && result.data.psr < 0.95
        ? "PSR이 저장 임계 0.95 미만입니다."
        : result.data.harness_json === null
          ? "grid 결과에는 집합 검증 증거가 없습니다. OOS 재검증을 권장합니다."
          : null;

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>스윕 결과 · {result.data.sweep_id}</CardTitle>
            <CardDescription>
              저장 요약만 조회 · 대표 run {shortHash(result.data.representative_run_id, 20)}
              {" · "}n={result.data.runs.length}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              value={metric}
              onChange={(event) => setMetric(event.target.value as MetricName)}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs"
              aria-label="스윕 지표"
            >
              {metrics.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant={view === "heatmap" ? "secondary" : "ghost"}
              onClick={() => setView("heatmap")}
            >
              <Grid3X3 className="mr-1 h-3.5 w-3.5" />
              히트맵
            </Button>
            <Button
              size="sm"
              variant={view === "list" ? "secondary" : "ghost"}
              onClick={() => setView("list")}
            >
              <List className="mr-1 h-3.5 w-3.5" />
              목록
            </Button>
          </div>
        </div>
        {aggregateRisk && (
          <div className="mt-3 flex items-center gap-2 rounded-md border border-amber-500/25 bg-amber-500/10 p-2 text-xs text-amber-200">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            과적합 경고 · {aggregateRisk}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {view === "heatmap" ? (
          <div className="overflow-x-auto">
            <div
              className="grid min-w-[560px] gap-2"
              style={{
                gridTemplateColumns: `minmax(90px,auto) repeat(${xValues.length}, minmax(100px,1fr))`,
              }}
            >
              <div className="p-2 text-[10px] text-muted-foreground">
                {yAxis ? `${yAxis} ↓ / ${xAxis} →` : `${xAxis} →`}
              </div>
              {xValues.map((value) => (
                <div
                  key={value}
                  className="truncate p-2 text-center font-mono text-[10px]"
                  title={value}
                >
                  {value}
                </div>
              ))}
              {yValues.map((yValue) => (
                <Fragment key={yValue}>
                  <div className="p-2 font-mono text-xs">
                    {yValue}
                  </div>
                  {xValues.map((xValue) => {
                    const item = result.data.runs.find((candidate) => {
                      const x =
                        xAxis === "run"
                          ? candidate.run.run_name
                          : parameterValue(candidate, xAxis);
                      const y = yAxis ? parameterValue(candidate, yAxis) : "all";
                      return x === xValue && y === yValue;
                    });
                    return (
                      <SweepCell
                        key={`${yValue}-${xValue}`}
                        item={item}
                        metric={metric}
                        best={best}
                        selected={Boolean(item && selected.includes(item.run.run_id))}
                        onSelect={() => {
                          if (!item) return;
                          setSelected((current) =>
                            current.includes(item.run.run_id)
                              ? current.filter((runId) => runId !== item.run.run_id)
                              : [...current, item.run.run_id],
                          );
                        }}
                      />
                    );
                  })}
                </Fragment>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {result.data.runs.map((item) => (
              <button
                key={item.run.run_id}
                type="button"
                onClick={() =>
                  setSelected((current) =>
                    current.includes(item.run.run_id)
                      ? current.filter((runId) => runId !== item.run.run_id)
                      : [...current, item.run.run_id],
                  )
                }
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg border p-3 text-left",
                  selected.includes(item.run.run_id) && "border-teal-400 bg-teal-500/10",
                )}
              >
                <span className="grid h-5 w-5 place-items-center rounded border">
                  {selected.includes(item.run.run_id) && <Check className="h-3 w-3" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs font-medium">
                    {item.run.run_name}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {JSON.stringify(item.run.params_json)}
                  </span>
                </span>
                <span className="tabular text-sm font-semibold">
                  {formatMetric(metricValue(item, metric), {
                    style:
                      metric === "mdd" || metric === "win_rate"
                        ? "percent"
                        : "decimal",
                  })}
                </span>
              </button>
            ))}
          </div>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t pt-4">
          <span className="text-xs text-muted-foreground">
            선택 {selectedItems.length}셀
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={selectedItems.length === 0}
            onClick={() => {
              basket.add(
                selectedItems.map((item) => ({
                  run_id: item.run.run_id,
                  run_name: item.run.run_name,
                  strategy_name: item.run.strategy_name,
                  symbol: item.run.symbol,
                  timeframe: item.run.timeframe,
                })),
              );
            }}
          >
            <GitCompareArrows className="mr-1.5 h-3.5 w-3.5" />
            비교 담기
          </Button>
          <Button
            size="sm"
            disabled={selectedItems.length !== 1}
            onClick={() =>
              navigate(
                `/runs/${encodeURIComponent(selectedItems[0]?.run.run_id ?? "")}`,
              )
            }
          >
            <Maximize2 className="mr-1.5 h-3.5 w-3.5" />
            셀 상세
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

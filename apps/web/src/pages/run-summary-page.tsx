import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clipboard,
  Database,
  GitCompareArrows,
  HeartPulse,
  LockKeyhole,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { useLocation } from "wouter";

import type { RunSummary } from "../api/client";
import { Badge, type BadgeProps } from "../components/ui/badge";
import { EquityDrawdownTab } from "../components/evidence/equity-drawdown-tab";
import { IntegrityCostTab } from "../components/evidence/integrity-cost-tab";
import { TradeDrawer } from "../components/evidence/trade-drawer";
import { TradesTab } from "../components/evidence/trades-tab";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { useComparisonBasket } from "../contexts/comparison-basket";
import { useRun, useRunSummary } from "../hooks/use-catalog";
import { useTrades } from "../hooks/use-evidence";
import {
  cn,
  formatDecimalString,
  formatMetric,
  formatPeriod,
  formatRatioPercent,
  formatTimestamp,
  shortHash,
} from "../lib/utils";

function MetricTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border bg-background/45 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="tabular mt-1 text-lg font-semibold tracking-tight">{value}</p>
      {hint && <p className="mt-0.5 text-[10px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Definition({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 text-xs", mono && "font-mono")}>{value}</dd>
    </div>
  );
}

function CopyHash({ value }: { value: string | null }) {
  if (!value) return <span>—</span>;
  return (
    <button
      type="button"
      onClick={() => void navigator.clipboard.writeText(value)}
      className="inline-flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground hover:text-foreground"
      title={value}
    >
      {shortHash(value, 14)}
      <Clipboard className="h-3 w-3" />
    </button>
  );
}

function decisionVariant(verdict: string | null): BadgeProps["variant"] {
  if (verdict === "pass") return "success";
  if (!verdict) return "secondary";
  return verdict.includes("fail") || verdict.includes("not_")
    ? "destructive"
    : "warning";
}

function SummaryOverview({ summary }: { summary: RunSummary }) {
  const costs = [
    ["Gross PnL", summary.gross_pnl_total],
    ["Fee", summary.total_fee],
    ["Slippage", summary.total_slippage],
    ["Funding", summary.total_funding],
    ["Liquidation penalty", summary.total_liquidation_penalty],
    ["Net PnL", summary.net_pnl_total],
  ] as const;

  return (
    <div className="space-y-4">
      <Card
        className={cn(
          "border-l-4",
          summary.gate_verdict === "pass"
            ? "border-l-emerald-500"
            : "border-l-amber-500",
        )}
      >
        <CardContent className="p-5">
          <div className="flex flex-wrap items-start gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-muted">
              {summary.gate_verdict === "pass" ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-amber-400" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">GATE</span>
                <Badge variant={decisionVariant(summary.gate_verdict)}>
                  {summary.gate_verdict ?? "not evaluated"}
                </Badge>
                <span className="text-xs font-medium text-muted-foreground">ROUTE</span>
                <Badge variant="outline">{summary.decision_route ?? "—"}</Badge>
                <span className="text-xs font-medium text-muted-foreground">ENVELOPE</span>
                <Badge variant="secondary">{summary.envelope_result ?? "—"}</Badge>
              </div>
              <p className="mt-3 text-sm leading-relaxed">
                {summary.decision_rationale ?? "저장된 판정 근거가 없습니다."}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                OOS degradation
              </p>
              <p className="tabular mt-1 text-base font-semibold">
                {formatMetric(summary.oos_degradation, {
                  style: "percent",
                  maximumFractionDigits: 1,
                })}
              </p>
            </div>
          </div>
          {(summary.gate_failed_json !== null ||
            summary.envelope_deviated_json !== null) && (
            <details className="mt-4 rounded-lg border bg-background/40 p-3 text-xs">
              <summary className="cursor-pointer text-muted-foreground">
                저장된 판정 상세 보기
              </summary>
              <pre className="mt-3 max-h-44 overflow-auto whitespace-pre-wrap text-[11px]">
                {JSON.stringify(
                  {
                    gate_failed: summary.gate_failed_json,
                    envelope_deviated: summary.envelope_deviated_json,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>핵심 지표</CardTitle>
          <CardDescription>
            backtest_summary에 저장된 통계량을 그대로 표시합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          <MetricTile label="PF" value={formatMetric(summary.pf)} />
          <MetricTile label="Sortino" value={formatMetric(summary.sortino)} />
          <MetricTile label="Calmar / MAR" value={formatMetric(summary.calmar_or_mar)} />
          <MetricTile label="SQN" value={formatMetric(summary.sqn)} />
          <MetricTile label="Sharpe" value={formatMetric(summary.sharpe)} />
          <MetricTile label="PSR" value={formatMetric(summary.psr)} />
          <MetricTile
            label="MDD"
            value={formatMetric(summary.mdd, {
              style: "percent",
              maximumFractionDigits: 2,
            })}
          />
          <MetricTile
            label="Risk of ruin"
            value={formatMetric(summary.ror, {
              style: "percent",
              maximumFractionDigits: 2,
            })}
          />
          <MetricTile label="Ulcer" value={formatMetric(summary.ulcer)} />
          <MetricTile label="Kelly" value={formatMetric(summary.kelly)} />
          <MetricTile
            label="Win rate"
            value={formatMetric(summary.win_rate, {
              style: "percent",
              maximumFractionDigits: 1,
            })}
          />
          <MetricTile
            label="Trades"
            value={formatMetric(summary.trade_count)}
            hint={`W ${summary.win_count} · L ${summary.loss_count} · R 제외 ${summary.r_excluded_count}`}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <HeartPulse className="h-4 w-4 text-teal-400" />
              <CardTitle>데이터 건강도</CardTitle>
            </div>
            <CardDescription>저장된 커버리지·무결성 진단입니다.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              <MetricTile
                label="Coverage"
                value={formatMetric(summary.data_coverage_ratio, {
                  style: "percent",
                  maximumFractionDigits: 2,
                })}
                hint={`${summary.observed_candle_count.toLocaleString()} / ${summary.expected_candle_count.toLocaleString()} candles`}
              />
              <MetricTile
                label="Integrity"
                value={summary.integrity_status}
                hint={summary.integrity_passed ? "passed" : "diagnostic required"}
              />
              <MetricTile
                label="Max gap"
                value={`${summary.max_consecutive_gap_bars} bars`}
                hint={`${summary.max_consecutive_gap_seconds.toLocaleString()} seconds`}
              />
              <MetricTile
                label="Gap exits"
                value={summary.data_gap_exit_count.toLocaleString()}
                hint={`source absent ${summary.source_absent_gap_count.toLocaleString()}`}
              />
            </div>
            {summary.integrity_failed_json !== null && (
              <details className="mt-3 rounded-lg border bg-background/40 p-3 text-xs">
                <summary className="cursor-pointer text-muted-foreground">
                  무결성 실패 상세
                </summary>
                <pre className="mt-3 max-h-44 overflow-auto whitespace-pre-wrap text-[11px]">
                  {JSON.stringify(summary.integrity_failed_json, null, 2)}
                </pre>
              </details>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-teal-400" />
              <CardTitle>비용 분해</CardTitle>
            </div>
            <CardDescription>
              Decimal 문자열을 변환·합산하지 않고 저장값 그대로 표시합니다.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
            {costs.map(([label, value]) => (
              <div key={label} className="border-b pb-2">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  {label}
                </p>
                <p className="tabular mt-1 text-sm font-medium">
                  {formatDecimalString(value)}
                </p>
              </div>
            ))}
            <div className="border-b pb-2">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Initial capital
              </p>
              <p className="tabular mt-1 text-sm font-medium">
                {formatDecimalString(summary.initial_capital)}
              </p>
            </div>
            <div className="border-b pb-2">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Final equity
              </p>
              <p className="tabular mt-1 text-sm font-medium">
                {formatDecimalString(summary.final_equity)}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function RunSummaryPage({ runId }: { runId: string }) {
  const [, navigate] = useLocation();
  const runQuery = useRun(runId);
  const summaryQuery = useRunSummary(runId);
  const tradesQuery = useTrades(runId);
  const basket = useComparisonBasket();
  const [selectedTradeId, setSelectedTradeId] = useState<number | null>(null);

  if (runQuery.isLoading || summaryQuery.isLoading) {
    return (
      <div className="mx-auto max-w-[1500px] space-y-4 p-4 md:p-6">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (runQuery.isError || summaryQuery.isError || !runQuery.data || !summaryQuery.data) {
    const message =
      runQuery.error?.message ??
      summaryQuery.error?.message ??
      "실행 정보를 불러오지 못했습니다.";
    return (
      <div className="grid min-h-[calc(100vh-3.5rem)] place-items-center p-6 text-center">
        <div>
          <XCircle className="mx-auto h-8 w-8 text-red-400" />
          <p className="mt-3 font-medium">실행 요약을 열 수 없습니다.</p>
          <p className="mt-1 text-sm text-muted-foreground">{message}</p>
          <Button className="mt-4" onClick={() => navigate("/runs")}>
            카탈로그로 돌아가기
          </Button>
        </div>
      </div>
    );
  }

  const run = runQuery.data;
  const summaryEnvelope = summaryQuery.data;
  const inBasket = basket.includes(run.run_id);

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 p-4 md:p-6">
      <Button variant="ghost" size="sm" onClick={() => navigate("/runs")}>
        <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
        카탈로그
      </Button>

      <Card className="overflow-hidden shadow-glow">
        <div className="border-b border-primary/10 bg-primary/[0.035] px-5 py-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={
                    run.status === "FAILED"
                      ? "destructive"
                      : run.status === "RUNNING"
                        ? "warning"
                        : "success"
                  }
                >
                  {run.status}
                </Badge>
                <Badge variant="outline">READ ONLY</Badge>
                <span className="text-xs text-muted-foreground">
                  {formatTimestamp(run.created_at)}
                </span>
              </div>
              <h1 className="mt-3 truncate text-xl font-semibold tracking-tight md:text-2xl">
                {run.run_id}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {run.strategy_name} v{run.strategy_version} · {run.symbol} ·{" "}
                {run.timeframe} · {run.market_type} ·{" "}
                {formatPeriod(run.period_start, run.period_end)}
              </p>
            </div>
            <Button
              variant={inBasket ? "secondary" : "default"}
              onClick={() => {
                if (inBasket) {
                  basket.remove(run.run_id);
                } else {
                  basket.add([
                    {
                      run_id: run.run_id,
                      run_name: run.run_name,
                      strategy_name: run.strategy_name,
                      symbol: run.symbol,
                      timeframe: run.timeframe,
                    },
                  ]);
                }
              }}
            >
              <GitCompareArrows className="mr-2 h-4 w-4" />
              {inBasket ? "비교에서 빼기" : "비교에 담기"}
            </Button>
          </div>
        </div>
        <CardContent className="p-5">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4 xl:grid-cols-6">
            <Definition label="Run name" value={run.run_name} />
            <Definition label="Strategy ID" value={run.strategy_id} />
            <Definition label="Initial capital" value={formatDecimalString(run.initial_capital)} />
            <Definition
              label="Sizing"
              value={`${run.sizing_method} ${formatRatioPercent(
                run.risk_per_trade ?? run.position_size_pct,
              )}`}
            />
            <Definition label="Seed" value={run.seed.toLocaleString()} />
            <Definition label="Engine" value={run.engine_version} />
            <Definition label="Config hash" value={<CopyHash value={run.config_hash} />} />
            <Definition
              label="Source hash"
              value={<CopyHash value={run.source_data_hash} />}
            />
            <Definition label="Sweep" value={run.sweep_id ?? "—"} mono />
            <Definition label="Fold" value={run.fold_label ?? "—"} />
            <Definition label="Data source" value={run.data_source} />
            <Definition label="Core lib" value={run.core_lib_version} />
          </dl>
          {run.error_message && (
            <div className="mt-4 rounded-lg border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-200">
              <div className="flex items-center gap-2 font-medium">
                <AlertTriangle className="h-4 w-4" />
                실행 오류
              </div>
              <p className="mt-1 text-xs">{run.error_message}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="overview">
        <div className="overflow-x-auto scrollbar-thin">
          <TabsList className="min-w-max">
            <TabsTrigger value="overview">개요</TabsTrigger>
            <TabsTrigger value="equity">
              자본곡선·DD
            </TabsTrigger>
            <TabsTrigger value="trades">
              거래
            </TabsTrigger>
            <TabsTrigger value="chart" disabled>
              차트
            </TabsTrigger>
            <TabsTrigger value="signals" disabled>
              신호·의사결정
            </TabsTrigger>
            <TabsTrigger value="integrity">
              무결성·비용
            </TabsTrigger>
            <TabsTrigger value="research" disabled>
              조건부·노트
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="overview">
          {summaryEnvelope.summary ? (
            <SummaryOverview summary={summaryEnvelope.summary} />
          ) : (
            <Card>
              <CardContent className="grid min-h-64 place-items-center p-8 text-center">
                <div>
                  {summaryEnvelope.summary_status === "pending" ? (
                    <HeartPulse className="mx-auto h-8 w-8 animate-pulse text-amber-400" />
                  ) : (
                    <LockKeyhole className="mx-auto h-8 w-8 text-muted-foreground" />
                  )}
                  <p className="mt-3 font-medium">저장된 요약이 아직 없습니다.</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    상태: {summaryEnvelope.run_status} · 요약:{" "}
                    {summaryEnvelope.summary_status}
                  </p>
                  <p className="mt-2 max-w-lg text-xs text-muted-foreground">
                    이 화면은 지표를 재계산하지 않습니다. Engine finalize 후 저장된
                    backtest_summary가 생기면 표시됩니다.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
        <TabsContent value="equity">
          <EquityDrawdownTab runId={runId} onSelectTrade={setSelectedTradeId} />
        </TabsContent>
        <TabsContent value="trades">
          <TradesTab runId={runId} onSelectTrade={setSelectedTradeId} />
        </TabsContent>
        <TabsContent value="integrity">
          <IntegrityCostTab runId={runId} summary={summaryEnvelope.summary} />
        </TabsContent>
      </Tabs>

      <TradeDrawer
        runId={runId}
        trades={tradesQuery.data ?? []}
        selectedTradeId={selectedTradeId}
        onSelect={setSelectedTradeId}
        onClose={() => setSelectedTradeId(null)}
      />

      <div className="flex items-center justify-center gap-2 py-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5 text-teal-500" />
        Stored summary · no client recomputation
      </div>
    </div>
  );
}

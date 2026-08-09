import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FlaskConical,
  LoaderCircle,
  Play,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "wouter";

import {
  apiClient,
  requestErrorMessage,
  type JobStatus,
  type PreregistrationInput,
  type RunConfigInput,
  type RunSubmission,
  type StrategyOption,
  type SweepAxis,
  type SweepSubmission,
} from "../api/client";
import { ResearchHelpDialog } from "../components/research-help-dialog";
import { StrategyParamHelpDialog } from "../components/strategy-param-help-dialog";
import { SweepResults } from "../components/sweep-results";
import { Badge, type BadgeProps } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { DateTimePickerField } from "../components/ui/date-time-picker";
import { GuidedInput } from "../components/ui/guided-input";
import {
  useRunJobs,
  type TrackedJob,
  type TrackedSweep,
} from "../contexts/run-jobs";
import { useCoverage } from "../hooks/use-p2b";
import {
  axisValuesError,
  axisValuesHint,
  defaultAxisValues,
} from "../lib/sweep-axis";
import {
  cn,
  formatTimestamp,
  fromDisplayZoneInput,
  shortHash,
  toDisplayZoneInput,
} from "../lib/utils";

type PrimaryMetric = NonNullable<PreregistrationInput["primary_metric"]>;
type SizingMethod = NonNullable<RunConfigInput["sizing_method"]>;
type IndicatorMode = NonNullable<RunConfigInput["indicator_mode"]>;
type MarketType = RunConfigInput["market_type"];
// Not the generated union. A money-management policy is deployed as a file, so
// the modes a backend accepts are whatever it has registered; the generated
// schema only records the ones that were deployed when it was generated. The
// selectable list comes from the strategy's supported_money_management instead.
type MoneyManagementMode = string;
type SweepType = SweepSubmission["type"];

interface FormState {
  strategyId: string;
  params: string;
  moneyManagementMode: MoneyManagementMode;
  manualLeverage: string;
  manualRewardRisk: string;
  manualAtrStopMultiple: string;
  turtleNPeriod: string;
  turtleStopNMultiple: string;
  turtleLeverageCap: string;
  // Settings for modes this page has no hand-written form for, edited as JSON
  // and kept per mode. One shared value carried one policy's settings into the
  // next policy, whose field names are entirely different.
  deployedMoneyManagement: Record<string, string>;
  symbol: string;
  exchange: string;
  timeframe: string;
  marketType: MarketType;
  dataSource: string;
  start: string;
  end: string;
  initialCapital: string;
  seed: string;
  sizingMethod: SizingMethod;
  riskPerTrade: string;
  positionSizePct: string;
  futuresTakerFeeRate: string;
  futuresEntrySlippageRate: string;
  exitSlippageRate: string;
  fundingFallbackRate: string;
  indicatorMode: IndicatorMode;
  explicitIndicators: string;
  profileRef: string;
  preregEnabled: boolean;
  hypothesis: string;
  primaryMetric: PrimaryMetric;
  successThreshold: string;
  failureThreshold: string;
  higherIsBetter: boolean;
  declaredBy: string;
}

const initialForm: FormState = {
  strategyId: "",
  params: "{}",
  moneyManagementMode: "",
  manualLeverage: "1",
  manualRewardRisk: "2",
  manualAtrStopMultiple: "2",
  turtleNPeriod: "20",
  turtleStopNMultiple: "2",
  turtleLeverageCap: "10",
  deployedMoneyManagement: {},
  symbol: "BTC/USDT:USDT",
  exchange: "binance",
  timeframe: "1h",
  marketType: "futures",
  dataSource: "crypto_data.ohlcv_futures",
  start: "2025-07-01T00:00",
  end: "2025-07-04T00:00",
  initialCapital: "10000",
  seed: "0",
  sizingMethod: "risk_based",
  riskPerTrade: "0.01",
  positionSizePct: "0.1",
  futuresTakerFeeRate: "0.0004",
  futuresEntrySlippageRate: "0.0005",
  exitSlippageRate: "0.0001",
  fundingFallbackRate: "0.0001",
  indicatorMode: "auto",
  explicitIndicators: "[]",
  profileRef: "vessel-reference-v1",
  preregEnabled: false,
  hypothesis: "",
  primaryMetric: "pf",
  successThreshold: "1.3",
  failureThreshold: "1.0",
  higherIsBetter: true,
  declaredBy: "",
};

const selectClass =
  "flex h-9 w-full rounded-md border border-input bg-background/70 px-3 py-1 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";
const textareaClass =
  "min-h-24 w-full rounded-md border border-input bg-background/70 px-3 py-2 font-mono text-xs shadow-sm outline-none placeholder:text-muted-foreground/70 focus-visible:ring-2 focus-visible:ring-ring";
// HTML min은 배타적 하한을 표현할 수 없어, 0 초과를 강제할 명시적인 최소 양수를 둔다.
const POSITIVE_NUMBER_INPUT_MIN = "0.000000000001";
// HTML bounds are inclusive, so "less than one" is expressed as the largest value
// the server still accepts rather than as one.
const SPLIT_INPUT_MAX = "0.999999999999";
const MONEY_MANAGEMENT_PARAM_NAMES = new Set([
  "leverage",
  "reward_risk",
  "atr_stop_multiple",
]);

function Label({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("grid gap-1.5 text-xs font-medium", className)}>
      {children}
    </label>
  );
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error(`${label}은 JSON 객체여야 합니다.`);
  }
  return parsed as Record<string, unknown>;
}

function parseIndicators(value: string): Record<string, unknown>[] {
  const parsed: unknown = JSON.parse(value);
  if (
    !Array.isArray(parsed) ||
    parsed.some((item) => typeof item !== "object" || item === null || Array.isArray(item))
  ) {
    throw new Error("명시 지표는 JSON 객체 배열이어야 합니다.");
  }
  return parsed as Record<string, unknown>[];
}

function parseAxisValues(
  value: string,
  label: string,
  parameter: string,
): SweepAxis["values"] {
  const parsed: unknown = JSON.parse(value);
  if (
    !Array.isArray(parsed) ||
    parsed.length < 2 ||
    parsed.some(
      (item) =>
        !["string", "number", "boolean"].includes(typeof item) ||
        (typeof item === "number" && !Number.isFinite(item)),
    )
  ) {
    throw new Error(`${label} 값은 스칼라 두 개 이상의 JSON 배열이어야 합니다.`);
  }
  const values = parsed as SweepAxis["values"];
  const ruleError = axisValuesError(parameter, values, label);
  if (ruleError) throw new Error(ruleError);
  return values;
}

function utcIso(value: string, label: string): string {
  // The field is a KST wall clock, so it is read in KST rather than in whatever zone
  // the viewer's machine happens to use. Otherwise the same entry would mean different
  // instants on different machines, and would not match what the catalog displays.
  const date = fromDisplayZoneInput(value);
  if (Number.isNaN(date.getTime())) throw new Error(`${label} 시간이 올바르지 않습니다.`);
  return date.toISOString();
}

function localDateTime(value: string): string {
  return toDisplayZoneInput(value);
}

function inferredMarketType(symbol: string): MarketType {
  return symbol.includes(":") ? "futures" : "spot";
}

function inferredDataSource(marketType: MarketType): string {
  return marketType === "futures"
    ? "crypto_data.ohlcv_futures"
    : "crypto_data.ohlcv";
}

function automaticRunName(strategyId: string, symbol: string): string {
  const strategy = strategyId
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const asset = (symbol.split("/")[0] ?? "asset")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `bt-${strategy || "strategy"}-${asset || "asset"}`
    .slice(0, 24)
    .replace(/-+$/g, "");
}

function paramsForDisplay(value: string): Record<string, unknown> {
  try {
    return parseObject(value, "전략 파라미터");
  } catch {
    return {};
  }
}

function strategyOnlyParams(
  params: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([name]) => !MONEY_MANAGEMENT_PARAM_NAMES.has(name),
    ),
  );
}

function timeframeMilliseconds(timeframe: string): number | null {
  const match = /^([1-9]\d*)([mhd])$/.exec(timeframe);
  if (!match) return null;
  const units = { m: 60_000, h: 3_600_000, d: 86_400_000 } as const;
  return Number(match[1]) * units[match[2] as keyof typeof units];
}

function alignedDefaultSplit(
  startValue: string,
  endValue: string,
  timeframe: string,
): string {
  const start = new Date(startValue).getTime();
  const end = new Date(endValue).getTime();
  const interval = timeframeMilliseconds(timeframe);
  if (!Number.isFinite(start) || !Number.isFinite(end) || !interval || start >= end) {
    return "0.5";
  }
  const earliest = Math.ceil((start + 1) / interval) * interval;
  const latest = Math.floor((end - 1) / interval) * interval;
  if (earliest > latest) return "0.5";
  const midpoint = Math.round(((start + end) / 2) / interval) * interval;
  const boundary = Math.min(latest, Math.max(earliest, midpoint));
  return ((boundary - start) / (end - start)).toString();
}

function isBuiltInMoneyManagement(mode: MoneyManagementMode): boolean {
  return mode === "manual" || mode === "turtle";
}

function settingsJson(source: Record<string, unknown>): string {
  // The mode itself is chosen by the select above, so it is not part of what the
  // operator edits; leaving it in would let the two disagree.
  const rest = Object.fromEntries(
    Object.entries(source).filter(([key]) => key !== "mode"),
  );
  return JSON.stringify(rest, null, 2);
}

function moneyManagementLabel(mode: MoneyManagementMode): string {
  // The two built-in policies have names an operator recognizes. A deployed
  // policy is shown by its registered mode, which is the only name it has here.
  if (mode === "manual") return "직접 설정";
  if (mode === "turtle") return "Turtle 자동 관리";
  return mode;
}

const UNRUNNABLE_REASON_LABELS: Record<
  NonNullable<StrategyOption["unrunnable_reason"]>,
  string
> = {
  catalog_only: "등록 정보는 있지만 배포된 코드가 없습니다.",
  allowlist_only: "배포된 코드는 있지만 등록 정보가 없습니다.",
  identity_mismatch: "등록 정보와 배포 코드의 신원이 일치하지 않습니다.",
  inactive: "등록 정보에서 비활성화된 전략입니다.",
  deprecated: "폐기된 전략입니다.",
  declaration_mismatch: "등록 정보와 배포 코드의 실행 선언이 일치하지 않습니다.",
  declaration_read_failed: "배포 코드의 실행 선언을 읽지 못했습니다.",
};

function unrunnableReasonLabel(reason: StrategyOption["unrunnable_reason"]): string {
  return reason
    ? UNRUNNABLE_REASON_LABELS[reason]
    : "서버가 이 전략을 실행할 수 없다고 판단했습니다.";
}

interface RunReadiness {
  runnable: boolean;
  reason: string | null;
  selectedStrategy: StrategyOption | null;
  usesMoneyManagement: boolean;
}

function assessRunReadiness({
  data,
  isPending,
  isError,
  isRefetchError,
  form,
  strategyAlignmentPending,
}: {
  data: StrategyOption[] | undefined;
  isPending: boolean;
  isError: boolean;
  isRefetchError: boolean;
  form: FormState;
  strategyAlignmentPending: boolean;
}): RunReadiness {
  const blocked = (
    reason: string,
    selectedStrategy: StrategyOption | null = null,
  ): RunReadiness => ({
    runnable: false,
    reason,
    selectedStrategy,
    usesMoneyManagement: false,
  });

  if (isRefetchError || (isError && data !== undefined)) {
    return blocked(
      "이전 전략 목록은 남아 있지만 최신 목록을 다시 받지 못했습니다. 다시 조회한 뒤 실행하세요.",
    );
  }
  if (isError) {
    return blocked("전략 목록을 처음 조회하지 못했습니다. 다시 조회하세요.");
  }
  if (isPending || data === undefined) {
    return blocked("전략 목록을 아직 받지 못했습니다.");
  }
  if (data.length === 0) {
    return blocked("실행할 전략이 없습니다.");
  }
  if (strategyAlignmentPending) {
    return blocked("새 전략에 맞춰 폼을 정렬하고 있습니다. 잠시 후 다시 실행하세요.");
  }
  if (!form.strategyId) {
    return blocked("실행할 전략을 선택하세요.");
  }

  const selectedStrategy = data.find(
    (strategy) => strategy.strategy_id === form.strategyId,
  );
  if (!selectedStrategy) {
    return blocked(
      `선택한 전략 ${form.strategyId}이 최신 전략 목록에 없습니다. 다른 전략을 선택하세요.`,
    );
  }
  if (!selectedStrategy.runnable) {
    return blocked(
      `${selectedStrategy.display_name} 전략을 실행할 수 없습니다. ${unrunnableReasonLabel(
        selectedStrategy.unrunnable_reason,
      )}`,
      selectedStrategy,
    );
  }
  if (!selectedStrategy.profile_id) {
    return blocked(
      `${selectedStrategy.display_name} 전략이 선언한 성격 정보 id를 읽을 수 없어 실행할 수 없습니다.`,
      selectedStrategy,
    );
  }
  if (!selectedStrategy.supported_timeframes.includes(form.timeframe)) {
    return blocked(
      `선택한 전략은 timeframe ${form.timeframe}을 지원하지 않습니다. 새 값을 선택하세요.`,
      selectedStrategy,
    );
  }

  const supportedModes = selectedStrategy.supported_money_management;
  if (supportedModes.length === 0) {
    return {
      runnable: true,
      reason: null,
      selectedStrategy,
      usesMoneyManagement: false,
    };
  }
  if (!form.moneyManagementMode) {
    return blocked(
      "이 전략의 기본 자금 관리 정책이 없어 아직 정책을 고르지 않았습니다. 정책을 선택하세요.",
      selectedStrategy,
    );
  }
  if (!supportedModes.includes(form.moneyManagementMode)) {
    return blocked(
      `선택한 전략은 자금 관리 ${form.moneyManagementMode} 정책을 더는 지원하지 않습니다. 새 값을 선택하세요.`,
      selectedStrategy,
    );
  }
  return {
    runnable: true,
    reason: null,
    selectedStrategy,
    usesMoneyManagement: true,
  };
}

function optionalNumber(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`숫자 값 '${value}'이 올바르지 않습니다.`);
  return parsed;
}

function buildMoneyManagement(
  form: FormState,
): NonNullable<RunConfigInput["money_management"]> {
  if (form.moneyManagementMode === "manual") {
    return {
      mode: "manual",
      leverage: Number(form.manualLeverage),
      reward_risk: Number(form.manualRewardRisk),
      atr_stop_multiple: Number(form.manualAtrStopMultiple),
    };
  }
  if (form.moneyManagementMode === "turtle") {
    return {
      mode: "turtle",
      n_period: Number(form.turtleNPeriod),
      n_timeframe: "1d",
      stop_n_multiple: Number(form.turtleStopNMultiple),
      leverage_cap: Number(form.turtleLeverageCap),
    };
  }
  // A deployed policy has settings this page cannot know the names of, so they
  // are submitted as the operator typed them. The cast is the boundary: the
  // generated union lists only the modes present when the schema was generated,
  // while the backend accepts whatever it has registered, and it validates this
  // object against the real policy.
  const typed = form.deployedMoneyManagement[form.moneyManagementMode] ?? "";
  return {
    // Spread first so the mode the select shows wins. The other order let a
    // "mode" key typed into the box submit a policy nobody chose.
    ...(typed.trim() ? parseObject(typed, "자금 관리 설정") : {}),
    mode: form.moneyManagementMode,
  } as NonNullable<RunConfigInput["money_management"]>;
}

function buildSubmission(
  form: FormState,
  selectedStrategy: StrategyOption,
  usesMoneyManagement: boolean,
): RunSubmission {
  const config: RunSubmission["config"] = {
    run_name: automaticRunName(form.strategyId, form.symbol),
    strategy_id: form.strategyId,
    params: strategyOnlyParams(parseObject(form.params, "전략 파라미터")),
    ...(usesMoneyManagement
      ? { money_management: buildMoneyManagement(form) }
      : {}),
    symbol: form.symbol.trim(),
    exchange: form.exchange.trim(),
    timeframe: form.timeframe.trim(),
    market_type: form.marketType,
    data_source: form.dataSource.trim(),
    start: utcIso(form.start, "시작"),
    end: utcIso(form.end, "종료"),
    initial_capital: form.initialCapital.trim(),
    seed: Number(form.seed),
    sizing_method: form.sizingMethod,
    risk_per_trade:
      form.sizingMethod === "risk_based"
        ? optionalNumber(form.riskPerTrade)
        : undefined,
    position_size_pct:
      form.sizingMethod === "pct" ? optionalNumber(form.positionSizePct) : undefined,
    cost_values: {
      futures_taker_fee_rate: form.futuresTakerFeeRate.trim(),
      futures_entry_slippage_rate: form.futuresEntrySlippageRate.trim(),
      exit_slippage_rate: form.exitSlippageRate.trim(),
      funding_fallback_rate: form.fundingFallbackRate.trim(),
    },
    indicator_mode: form.indicatorMode,
    explicit_indicators:
      form.indicatorMode === "explicit"
        ? parseIndicators(form.explicitIndicators)
        : [],
    trigger_feed: "tf_candle",
    fill_timing: "next_bar",
    profile_ref: selectedStrategy.profile_id!,
  };
  const prereg: PreregistrationInput | undefined = form.preregEnabled
    ? {
        hypothesis: form.hypothesis.trim() || undefined,
        primary_metric: form.primaryMetric,
        success_threshold: optionalNumber(form.successThreshold),
        failure_threshold: optionalNumber(form.failureThreshold),
        higher_is_better: form.higherIsBetter,
        declared_by: form.declaredBy.trim() || undefined,
      }
    : undefined;
  return { config, prereg };
}

export function restoredMoneyManagementMode(
  submission: RunSubmission,
): MoneyManagementMode {
  return submission.config.money_management?.mode ?? "";
}

function statusVariant(status: JobStatus["status"]): BadgeProps["variant"] {
  if (status === "SUCCEEDED") return "success";
  if (status === "RUNNING" || status === "QUEUED") return "warning";
  if (status === "FAILED") return "destructive";
  return "secondary";
}

function statusIcon(status: JobStatus["status"]) {
  if (status === "SUCCEEDED") return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
  if (status === "FAILED") return <XCircle className="h-4 w-4 text-red-400" />;
  if (status === "ORPHANED") return <AlertTriangle className="h-4 w-4 text-amber-400" />;
  if (status === "RUNNING") {
    return <LoaderCircle className="h-4 w-4 animate-spin text-teal-300" />;
  }
  return <Clock3 className="h-4 w-4 text-amber-300" />;
}

export function JobRow({
  job,
  onEdit,
}: {
  job: TrackedJob;
  onEdit: (submission: RunSubmission) => void;
}) {
  const status = job.status;
  return (
    <div className="rounded-lg border bg-background/45 p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="mt-0.5">{statusIcon(status.status)}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold">
              {job.submission.config.run_name}
            </p>
            <Badge variant={statusVariant(status.status)}>{status.status}</Badge>
            {status.catalog_status && (
              <Badge variant="outline">catalog {status.catalog_status}</Badge>
            )}
          </div>
          <p className="mt-1 font-mono text-[10px] text-muted-foreground">
            job {shortHash(status.job_id, 20)} · {formatTimestamp(job.submittedAt)}
          </p>
          {status.status === "QUEUED" && (
            <p className="mt-2 text-xs text-muted-foreground">
              단일 dry-run 워커가 앞선 실행을 마치면 시작합니다.
            </p>
          )}
          {status.status === "RUNNING" && (
            <div className="mt-3">
              <div
                role="progressbar"
                aria-label="실행 중"
                aria-valuetext="서버 수치 진행률 미제공"
                className="h-1.5 overflow-hidden rounded-full bg-muted"
              >
                <div className="h-full w-full animate-pulse bg-gradient-to-r from-transparent via-teal-400/80 to-transparent" />
              </div>
              <p className="mt-1.5 text-[10px] text-muted-foreground">
                서버가 수치 진행률을 제공하지 않아 완료율은 표시하지 않습니다.
              </p>
            </div>
          )}
          {status.error && (
            <div className="mt-3 rounded-md border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-200">
              <p className="font-semibold">{status.error.code}</p>
              <p className="mt-1 break-words">{status.error.message}</p>
            </div>
          )}
          {status.status === "ORPHANED" && (
            <p className="mt-3 text-xs text-amber-200">
              서버 재시작으로 실행 추적이 유실되었습니다. 카탈로그 진단 후 새 dry-run으로
              재시도하세요.
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {(status.status === "FAILED" || status.status === "ORPHANED") && (
            <Button variant="outline" size="sm" onClick={() => onEdit(job.submission)}>
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              폼 수정
            </Button>
          )}
          {status.status === "SUCCEEDED" && status.run_id && (
            <Button asChild size="sm">
              <Link href={`/runs/${encodeURIComponent(status.run_id)}`}>상세</Link>
            </Button>
          )}
        </div>
      </div>
      {status.status === "SUCCEEDED" && (
        <div className="mt-3 grid gap-1 border-t pt-3 font-mono text-[10px] text-muted-foreground sm:grid-cols-2">
          <span>run {status.run_id}</span>
          <span>evidence {shortHash(status.evidence_hash ?? "", 24)}</span>
        </div>
      )}
    </div>
  );
}

export function SweepJobRow({
  sweep,
  onSelectResult,
}: {
  sweep: TrackedSweep;
  onSelectResult: (sweepId: string) => void;
}) {
  return (
    <div className="rounded-lg border bg-background/45 p-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{statusIcon(sweep.status.status)}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold">
              {sweep.submission.config.run_name} · {sweep.submission.type}
            </p>
            <Badge variant={statusVariant(sweep.status.status)}>
              {sweep.status.status}
            </Badge>
          </div>
          <p className="mt-1 font-mono text-[10px] text-muted-foreground">
            job {shortHash(sweep.status.job_id, 20)} ·{" "}
            {formatTimestamp(sweep.submittedAt)}
          </p>
          {sweep.status.status === "RUNNING" && (
            <div className="mt-3">
              <div
                role="progressbar"
                aria-label="스윕 실행 중"
                aria-valuetext="서버 수치 진행률 미제공"
                className="h-1.5 overflow-hidden rounded-full bg-muted"
              >
                <div className="h-full w-full animate-pulse bg-gradient-to-r from-transparent via-teal-400/80 to-transparent" />
              </div>
              <p className="mt-1.5 text-[10px] text-muted-foreground">
                서버가 수치 진행률을 제공하지 않아 완료율은 표시하지 않습니다.
              </p>
            </div>
          )}
          {sweep.status.error && (
            <p className="mt-2 text-xs text-red-300">{sweep.status.error.message}</p>
          )}
          {sweep.status.sweep_id && (
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-[10px] text-muted-foreground">
                {sweep.status.sweep_id} · {sweep.status.run_count ?? "—"} runs ·
                representative {shortHash(sweep.status.run_id, 18)}
              </p>
              {sweep.status.status === "SUCCEEDED" && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onSelectResult(sweep.status.sweep_id!)}
                >
                  결과 보기
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function RunManagementPage() {
  const { jobs, sweeps, track, trackSweep } = useRunJobs();
  const formRef = useRef<HTMLFormElement>(null);
  const [form, setForm] = useState<FormState>(initialForm);
  const strategyDrafts = useRef<Record<string, FormState>>({});
  const strategyAlignmentRef = useRef<string | null>(null);
  const [strategyAlignmentPending, setStrategyAlignmentPending] = useState<
    string | null
  >(null);
  const axisContract = useRef<string | null>(null);
  const axisCandidatesPreviouslyAvailable = useRef(false);
  const [busy, setBusy] = useState<"trigger" | "sweep" | null>(null);
  // The sweep is a mode the run is submitted in, not a separate action. Keeping it
  // in form state means the choice is visible while the section is collapsed and
  // one submit button can serve both.
  const [sweepEnabled, setSweepEnabled] = useState(false);
  const [sweepType, setSweepType] = useState<SweepType>("grid");
  const [axisOneParameter, setAxisOneParameter] = useState("reward_risk");
  const [axisOneValues, setAxisOneValues] = useState("[1.5, 2.0, 2.5]");
  const [axisTwoEnabled, setAxisTwoEnabled] = useState(true);
  const [axisTwoParameter, setAxisTwoParameter] = useState("atr_stop_multiple");
  const [axisTwoValues, setAxisTwoValues] = useState("[1.5, 2.0]");
  const [folds, setFolds] = useState("3");
  const [split, setSplit] = useState(() =>
    alignedDefaultSplit(initialForm.start, initialForm.end, initialForm.timeframe),
  );
  const [splitCustomized, setSplitCustomized] = useState(false);
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const initialSweepId =
    typeof window === "undefined"
      ? ""
      : new URLSearchParams(window.location.search).get("sweep_id") ?? "";
  const [sweepLookup, setSweepLookup] = useState(initialSweepId);
  const [selectedSweepId, setSelectedSweepId] = useState<string | null>(
    initialSweepId || null,
  );

  const strategies = useQuery({
    queryKey: ["strategies"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/strategies");
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("전략 목록 응답이 비어 있습니다.");
      return data.data;
    },
  });
  const selectedStrategy = useMemo(
    () => strategies.data?.find((item) => item.strategy_id === form.strategyId),
    [form.strategyId, strategies.data],
  );
  const supportedMoneyManagement = useMemo(
    () => selectedStrategy?.supported_money_management ?? [],
    [selectedStrategy],
  );
  const moneyManagementSelectionInvalid = Boolean(
    selectedStrategy &&
      form.moneyManagementMode &&
      !selectedStrategy.supported_money_management.includes(form.moneyManagementMode),
  );
  const timeframeSelectionInvalid = Boolean(
    selectedStrategy &&
      !selectedStrategy.supported_timeframes.includes(form.timeframe),
  );
  const axisCandidates = useMemo(
    () => [
      ...Object.keys(
        strategyOnlyParams(selectedStrategy?.default_params ?? {}),
      ),
      // Only the two built-in policies have field names this page knows. A
      // deployed policy's settings are whatever it declares, so offering
      // Turtle's axes for it would sweep parameters that do not exist.
      ...(form.moneyManagementMode === "manual"
        ? [
            "money_management.leverage",
            "money_management.reward_risk",
            "money_management.atr_stop_multiple",
          ]
        : form.moneyManagementMode === "turtle"
          ? [
              "money_management.n_period",
              "money_management.stop_n_multiple",
              "money_management.leverage_cap",
            ]
          : []),
    ],
    [form.moneyManagementMode, selectedStrategy],
  );
  const strategyParams = useMemo(
    () => strategyOnlyParams(paramsForDisplay(form.params)),
    [form.params],
  );
  const strategyParamEntries = useMemo(
    () =>
      Object.entries({
        ...strategyOnlyParams(selectedStrategy?.default_params ?? {}),
        ...strategyParams,
      }),
    [selectedStrategy, strategyParams],
  );
  function currentRunReadiness(): RunReadiness {
    return assessRunReadiness({
      data: strategies.data,
      isPending: strategies.isPending,
      isError: strategies.isError,
      isRefetchError: strategies.isRefetchError,
      form,
      strategyAlignmentPending: Boolean(
        strategyAlignmentPending || strategyAlignmentRef.current,
      ),
    });
  }
  const runReadiness = currentRunReadiness();
  const gridAxesReady =
    Boolean(axisOneParameter.trim()) &&
    (!axisTwoEnabled ||
      (Boolean(axisTwoParameter.trim()) &&
        axisTwoParameter.trim() !== axisOneParameter.trim()));
  const gridSweepBlocked = sweepEnabled && sweepType === "grid" && !gridAxesReady;
  const coverage = useCoverage(form.dataSource, form.symbol, form.exchange);
  const coverageWarning = useMemo(() => {
    if (!coverage.data) return null;
    if (!coverage.data.available_from || !coverage.data.available_to) {
      return "선택한 데이터 소스·심볼·거래소 조합에는 1분봉이 없습니다.";
    }
    const requestedStart = new Date(form.start).getTime();
    const requestedEnd = new Date(form.end).getTime();
    const availableStart = new Date(coverage.data.available_from).getTime();
    const availableEnd = new Date(coverage.data.available_to).getTime();
    if (requestedStart < availableStart || requestedEnd > availableEnd) {
      return "요청 기간이 데이터 가용 구간을 벗어납니다. 실행 전 기간을 조정하세요.";
    }
    return null;
  }, [coverage.data, form.end, form.start]);

  useEffect(() => {
    if (
      strategyAlignmentPending &&
      form.strategyId === strategyAlignmentPending
    ) {
      strategyAlignmentRef.current = null;
      setStrategyAlignmentPending(null);
    }
  }, [form.strategyId, strategyAlignmentPending]);

  useEffect(() => {
    const marketType = inferredMarketType(form.symbol);
    setForm((current) => ({
      ...current,
      exchange: "binance",
      marketType,
      dataSource: inferredDataSource(marketType),
    }));
  }, [form.symbol]);

  useEffect(() => {
    const contract = `${form.strategyId}\u0000${form.moneyManagementMode}\u0000${axisCandidates.join("\u0000")}`;
    if (axisContract.current === contract) return;
    axisContract.current = contract;
    const candidatesWereAvailable = axisCandidatesPreviouslyAvailable.current;
    axisCandidatesPreviouslyAvailable.current = axisCandidates.length > 0;
    if (axisCandidates.length === 0) {
      setAxisOneParameter("");
      setAxisOneValues("[]");
      setAxisTwoEnabled(false);
      setAxisTwoParameter("");
      setAxisTwoValues("[]");
      return;
    }
    const nextOne = axisCandidates.includes(axisOneParameter)
      ? axisOneParameter
      : axisCandidates[0];
    const nextTwo = axisCandidates.includes(axisTwoParameter)
      && axisTwoParameter !== nextOne
      ? axisTwoParameter
      : axisCandidates.find((candidate) => candidate !== nextOne);
    if (axisOneParameter !== nextOne) setAxisOneParameter(nextOne);
    if (nextTwo && axisTwoParameter !== nextTwo) setAxisTwoParameter(nextTwo);
    if (!nextTwo) {
      setAxisTwoEnabled(false);
    } else if (!candidatesWereAvailable) {
      setAxisTwoEnabled(true);
    }
  }, [axisCandidates, axisOneParameter, axisTwoParameter, form.moneyManagementMode, form.strategyId]);

  // A parameter change carries its own valid starting values: sweeping leverage
  // over [1.5, 2.0, 2.5] would produce runs the schema rejects one by one.
  useEffect(() => {
    setAxisOneValues((current) => defaultAxisValues(axisOneParameter, current));
  }, [axisOneParameter]);

  useEffect(() => {
    setAxisTwoValues((current) => defaultAxisValues(axisTwoParameter, current));
  }, [axisTwoParameter]);

  useEffect(() => {
    if (splitCustomized) return;
    setSplit(alignedDefaultSplit(form.start, form.end, form.timeframe));
  }, [form.end, form.start, form.timeframe, splitCustomized]);

  useEffect(() => {
    const onPopState = () => {
      const sweepId = new URLSearchParams(window.location.search).get("sweep_id") ?? "";
      setSweepLookup(sweepId);
      setSelectedSweepId(sweepId || null);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (selectedSweepId) return;
    const latestSucceeded = sweeps.find(
      (sweep) =>
        sweep.status.status === "SUCCEEDED" && Boolean(sweep.status.sweep_id),
    )?.status.sweep_id;
    if (latestSucceeded) {
      setSweepLookup(latestSucceeded);
      setSelectedSweepId(latestSucceeded);
    }
  }, [selectedSweepId, sweeps]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateStrategyParam(
    parameter: string,
    rawValue: string | boolean,
    exampleValue: unknown,
  ) {
    setForm((current) => {
      const params = paramsForDisplay(current.params);
      const value =
        typeof rawValue === "boolean"
          ? rawValue
          : typeof exampleValue === "number" && rawValue !== ""
            ? Number(rawValue)
            : rawValue;
      return {
        ...current,
        params: JSON.stringify({ ...params, [parameter]: value }, null, 2),
      };
    });
  }

  function selectStrategy(strategyId: string) {
    strategyAlignmentRef.current = strategyId || null;
    setStrategyAlignmentPending(strategyId || null);
    setForm((current) => {
      if (current.strategyId) {
        strategyDrafts.current[current.strategyId] = current;
      }
      if (!strategyId) {
        return {
          ...current,
          strategyId: "",
          params: "{}",
          moneyManagementMode: "",
        };
      }

      const saved = strategyDrafts.current[strategyId];
      if (saved) return { ...saved, strategyId };

      const strategy = strategies.data?.find(
        (item) => item.strategy_id === strategyId,
      );
      if (!strategy) {
        return {
          ...current,
          strategyId,
          params: "{}",
          moneyManagementMode: "",
        };
      }

      const defaultMoneyManagement = strategy.default_money_management ?? {};
      const declaredDefault =
        typeof defaultMoneyManagement.mode === "string"
          ? defaultMoneyManagement.mode
          : "";
      // A missing or filtered default remains unselected. Picking the first
      // remaining mode would make the screen override the strategy declaration.
      const mode = strategy.supported_money_management.includes(declaredDefault)
        ? declaredDefault
        : "";
      return {
        ...current,
        strategyId,
        params: JSON.stringify(
          strategyOnlyParams(strategy.default_params),
          null,
          2,
        ),
        moneyManagementMode: mode,
        manualLeverage: String(
          defaultMoneyManagement.leverage ?? current.manualLeverage,
        ),
        manualRewardRisk: String(
          defaultMoneyManagement.reward_risk ?? current.manualRewardRisk,
        ),
        manualAtrStopMultiple: String(
          defaultMoneyManagement.atr_stop_multiple ??
            current.manualAtrStopMultiple,
        ),
        deployedMoneyManagement:
          !mode || isBuiltInMoneyManagement(mode)
            ? current.deployedMoneyManagement
            : {
                ...current.deployedMoneyManagement,
                [mode]: settingsJson(defaultMoneyManagement),
              },
        timeframe: strategy.supported_timeframes.includes(current.timeframe)
          ? current.timeframe
          : (strategy.supported_timeframes[0] ?? current.timeframe),
      };
    });
  }

  function openSweepResult(sweepId: string) {
    const normalized = sweepId.trim();
    if (!normalized) return;
    const url = new URL(window.location.href);
    url.searchParams.set("sweep_id", normalized);
    window.history.pushState(null, "", url);
    setSweepLookup(normalized);
    setSelectedSweepId(normalized);
  }

  async function triggerRun() {
    const readiness = currentRunReadiness();
    if (!readiness.runnable) {
      setNotice({ kind: "error", message: readiness.reason ?? "실행할 수 없습니다." });
      return;
    }
    setBusy("trigger");
    setNotice(null);
    try {
      const submission = buildSubmission(
        form,
        readiness.selectedStrategy!,
        readiness.usesMoneyManagement,
      );
      const { data, error } = await apiClient.POST("/api/v1/runs", {
        body: submission,
      });
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("트리거 응답이 비어 있습니다.");
      track(data, submission);
      setNotice({
        kind: "success",
        message: `dry-run이 큐에 등록되었습니다. job ${shortHash(data.job_id, 16)}`,
      });
    } catch (error) {
      setNotice({
        kind: "error",
        message: error instanceof Error ? error.message : "dry-run을 트리거하지 못했습니다.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function triggerSweep() {
    const readiness = currentRunReadiness();
    if (!readiness.runnable) {
      setNotice({ kind: "error", message: readiness.reason ?? "실행할 수 없습니다." });
      return;
    }
    setBusy("sweep");
    setNotice(null);
    try {
      const base = buildSubmission(
        form,
        readiness.selectedStrategy!,
        readiness.usesMoneyManagement,
      );
      const submission: SweepSubmission = {
        type: sweepType,
        config: base.config,
        prereg: base.prereg,
        ...(sweepType === "grid"
          ? {
              axes: [
                {
                  parameter: axisOneParameter.trim(),
                  values: parseAxisValues(
                    axisOneValues,
                    "첫 번째 축",
                    axisOneParameter,
                  ),
                },
                ...(axisTwoEnabled
                  ? [
                      {
                        parameter: axisTwoParameter.trim(),
                        values: parseAxisValues(
                          axisTwoValues,
                          "두 번째 축",
                          axisTwoParameter,
                        ),
                      },
                    ]
                  : []),
              ],
            }
          : sweepType === "walk_forward"
            ? { folds: Number(folds) }
            : { split: Number(split) }),
      };
      const { data, error } = await apiClient.POST("/api/v1/sweeps", {
        body: submission,
      });
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("스윕 트리거 응답이 비어 있습니다.");
      trackSweep(data, submission);
      setNotice({
        kind: "success",
        message: `스윕 dry-run이 큐에 등록되었습니다. job ${shortHash(data.job_id, 16)}`,
      });
    } catch (error) {
      setNotice({
        kind: "error",
        message:
          error instanceof Error ? error.message : "스윕을 트리거하지 못했습니다.",
      });
    } finally {
      setBusy(null);
    }
  }

  function loadSubmission(submission: RunSubmission) {
    const config = submission.config;
    const prereg = submission.prereg;
    const moneyManagement = config.money_management;
    setForm((current) => {
      if (current.strategyId) {
        strategyDrafts.current[current.strategyId] = current;
      }
      return {
        ...current,
        strategyId: config.strategy_id,
        params: JSON.stringify(
          strategyOnlyParams(config.params ?? {}),
          null,
          2,
        ),
        moneyManagementMode: restoredMoneyManagementMode(submission),
        manualLeverage: String(
          moneyManagement?.mode === "manual"
            ? moneyManagement.leverage
            : current.manualLeverage,
        ),
        manualRewardRisk: String(
          moneyManagement?.mode === "manual"
            ? moneyManagement.reward_risk
            : current.manualRewardRisk,
        ),
        manualAtrStopMultiple: String(
          moneyManagement?.mode === "manual"
            ? moneyManagement.atr_stop_multiple
            : current.manualAtrStopMultiple,
        ),
        turtleNPeriod: String(
          moneyManagement?.mode === "turtle"
            ? moneyManagement.n_period
            : current.turtleNPeriod,
        ),
        turtleStopNMultiple: String(
          moneyManagement?.mode === "turtle"
            ? moneyManagement.stop_n_multiple
            : current.turtleStopNMultiple,
        ),
        turtleLeverageCap: String(
          moneyManagement?.mode === "turtle"
            ? moneyManagement.leverage_cap
            : current.turtleLeverageCap,
        ),
        deployedMoneyManagement:
          moneyManagement && !isBuiltInMoneyManagement(moneyManagement.mode)
            ? {
                ...current.deployedMoneyManagement,
                [moneyManagement.mode]: settingsJson(
                  moneyManagement as Record<string, unknown>,
                ),
              }
            : current.deployedMoneyManagement,
        symbol: config.symbol,
        exchange: config.exchange,
        timeframe: config.timeframe,
        marketType: config.market_type,
        dataSource: config.data_source,
        start: localDateTime(config.start),
        end: localDateTime(config.end),
        initialCapital: String(config.initial_capital),
        seed: String(config.seed),
        sizingMethod: config.sizing_method,
        riskPerTrade: String(config.risk_per_trade ?? current.riskPerTrade),
        positionSizePct: String(
          config.position_size_pct ?? current.positionSizePct,
        ),
        futuresTakerFeeRate: String(
          config.cost_values?.futures_taker_fee_rate ??
            current.futuresTakerFeeRate,
        ),
        futuresEntrySlippageRate: String(
          config.cost_values?.futures_entry_slippage_rate ??
            current.futuresEntrySlippageRate,
        ),
        exitSlippageRate: String(
          config.cost_values?.exit_slippage_rate ?? current.exitSlippageRate,
        ),
        fundingFallbackRate: String(
          config.cost_values?.funding_fallback_rate ?? current.fundingFallbackRate,
        ),
        indicatorMode: config.indicator_mode,
        explicitIndicators: JSON.stringify(
          config.explicit_indicators ?? [],
          null,
          2,
        ),
        profileRef: config.profile_ref,
        preregEnabled: Boolean(prereg),
        hypothesis: prereg?.hypothesis ?? "",
        primaryMetric: prereg?.primary_metric ?? "pf",
        successThreshold: String(prereg?.success_threshold ?? ""),
        failureThreshold: String(prereg?.failure_threshold ?? ""),
        higherIsBetter: prereg?.higher_is_better ?? true,
        declaredBy: prereg?.declared_by ?? "",
      };
    });
    setNotice({ kind: "success", message: "실패한 설정을 폼에 다시 불러왔습니다." });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 p-4 md:p-6">
      <section className="overflow-hidden rounded-xl border border-teal-500/25 bg-gradient-to-r from-teal-500/10 via-card to-card p-5">
        <div className="flex flex-wrap items-start gap-4">
          <div className="grid h-10 w-10 place-items-center rounded-lg border border-teal-500/25 bg-teal-500/10 text-teal-200">
            <FlaskConical className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-semibold">실행 관리</h1>
              <Badge className="border-teal-400/30 bg-teal-400/10 text-teal-200">
                DRY-RUN · 실주문 아님
              </Badge>
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted-foreground">
              이 화면은 백테스트 카탈로그와 Evidence만 생성합니다. 시장·신호 데이터는 읽기
              전용이며 주문·지갑 경로는 연결되지 않습니다.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-teal-500/15 bg-background/40 px-3 py-2 text-xs text-teal-200">
            <ShieldCheck className="h-4 w-4" />
            동시 실행 상한 1
          </div>
        </div>
      </section>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(360px,0.85fr)]">
        <form
          ref={formRef}
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            const readiness = currentRunReadiness();
            if (!readiness.runnable) {
              setNotice({
                kind: "error",
                message: readiness.reason ?? "실행할 수 없습니다.",
              });
              return;
            }
            if (gridSweepBlocked) return;
            if (sweepEnabled) {
              void triggerSweep();
              return;
            }
            void triggerRun();
          }}
        >
          <Card>
            <CardHeader>
              <CardTitle>새 백테스트 설정</CardTitle>
              <CardDescription>
                전략과 데이터 범위만 선택하세요. 나머지 실행 설정은 전략과 데이터셋에서
                자동으로 결정합니다.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <section className="grid gap-4 md:grid-cols-2">
                <Label className="md:col-span-2">
                  전략
                  <select
                    className={selectClass}
                    value={form.strategyId}
                    onChange={(event) => selectStrategy(event.target.value)}
                    disabled={
                      strategies.isPending ||
                      (strategies.isError && !strategies.data)
                    }
                    aria-invalid={!runReadiness.runnable}
                    title={runReadiness.reason ?? undefined}
                  >
                    <option value="">전략을 선택하세요</option>
                    {(strategies.data ?? []).map((strategy) => (
                      <option
                        key={strategy.strategy_id}
                        value={strategy.strategy_id}
                        disabled={!strategy.runnable || !strategy.profile_id}
                      >
                        {strategy.display_name} · {strategy.strategy_version}
                        {!strategy.runnable
                          ? ` · 실행 불가: ${unrunnableReasonLabel(strategy.unrunnable_reason)}`
                          : !strategy.profile_id
                            ? " · 실행 불가: 선언한 성격 정보 id가 없습니다."
                          : ""}
                      </option>
                    ))}
                    {form.strategyId && !selectedStrategy && (
                      <option value={form.strategyId} disabled>
                        {form.strategyId} · 최신 목록에 없음
                      </option>
                    )}
                  </select>
                </Label>
                {selectedStrategy && (
                  <div className="md:col-span-2 rounded-lg border bg-muted/25 p-3 text-xs text-muted-foreground">
                    최소 이력 {selectedStrategy.min_history}
                    {" · "}필수 지표{" "}
                    {selectedStrategy.required_indicators.length
                      ? selectedStrategy.required_indicators
                          .map((item) => String(item.name ?? "unknown"))
                          .join(", ")
                      : "전략이 자동 결정"}
                    {" · "}출처 {selectedStrategy.source}
                  </div>
                )}
                <div className="grid gap-1.5 text-xs font-medium md:col-span-2">
                  <span>전략 파라미터</span>
                  {strategyParamEntries.length ? (
                    <div className="grid gap-3 rounded-lg border bg-muted/10 p-4 sm:grid-cols-2">
                      {strategyParamEntries.map(([parameter, currentValue]) => {
                        const exampleValue =
                          selectedStrategy?.default_params[parameter] ??
                          currentValue;
                        return typeof exampleValue === "boolean" ? (
                          <label
                            key={parameter}
                            className="flex items-center gap-2 text-xs font-medium"
                          >
                            <input
                              type="checkbox"
                              checked={Boolean(strategyParams[parameter])}
                              onChange={(event) =>
                                updateStrategyParam(
                                  parameter,
                                  event.target.checked,
                                  exampleValue,
                                )
                              }
                              className="h-4 w-4 accent-teal-500"
                            />
                            {parameter}
                          </label>
                        ) : typeof exampleValue === "number" ||
                          typeof exampleValue === "string" ? (
                          <Label key={parameter}>
                            {parameter}
                            <GuidedInput
                              aria-label={`전략 파라미터 ${parameter}`}
                              hint={
                                typeof exampleValue === "number"
                                  ? "숫자 · 소수 가능"
                                  : "문자열"
                              }
                              type={
                                typeof exampleValue === "number" ? "number" : "text"
                              }
                              step={
                                typeof exampleValue === "number" ? "any" : undefined
                              }
                              value={String(
                                strategyParams[parameter] ?? exampleValue,
                              )}
                              onChange={(event) =>
                                updateStrategyParam(
                                  parameter,
                                  event.target.value,
                                  exampleValue,
                                )
                              }
                              required
                            />
                          </Label>
                        ) : null;
                      })}
                    </div>
                  ) : (
                    <p className="rounded-lg border bg-muted/10 p-3 font-normal text-muted-foreground">
                      이 전략에는 사용자가 조정할 기본 파라미터가 없습니다.
                    </p>
                  )}
                  <details className="rounded-lg border bg-muted/10 px-3 py-2 font-normal">
                    <summary className="cursor-pointer text-xs text-muted-foreground">
                      JSON 직접 편집
                    </summary>
                    <label
                      htmlFor="strategy-parameters"
                      className="mt-3 grid gap-1.5 text-xs font-medium"
                    >
                      전략 파라미터 JSON
                      <textarea
                        id="strategy-parameters"
                        className={textareaClass}
                        value={form.params}
                        onChange={(event) => update("params", event.target.value)}
                        spellCheck={false}
                      />
                    </label>
                  </details>
                </div>
                {selectedStrategy && supportedMoneyManagement.length > 0 ? (
                  <div className="grid gap-3 rounded-lg border border-teal-500/20 bg-teal-500/5 p-4 md:col-span-2">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-teal-100">
                        자금 관리
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        전략 판단은 그대로 두고 손절·수량·레버리지만 선택한 정책이
                        계산합니다.
                      </p>
                    </div>
                    {form.moneyManagementMode === "manual" && (
                      <StrategyParamHelpDialog strategyId={form.strategyId} />
                    )}
                  </div>
                  {supportedMoneyManagement.length > 1 ||
                  moneyManagementSelectionInvalid ||
                  !form.moneyManagementMode ? (
                    <Label>
                      자금 관리 방법
                      <select
                        aria-label="자금 관리 방법"
                        className={selectClass}
                        value={form.moneyManagementMode}
                        disabled={!runReadiness.selectedStrategy?.runnable}
                        aria-invalid={!runReadiness.runnable}
                        title={runReadiness.reason ?? undefined}
                        onChange={(event) => {
                          const mode = event.target
                            .value as MoneyManagementMode;
                          const declared =
                            selectedStrategy?.default_money_management ?? {};
                          setForm((current) => ({
                            ...current,
                            moneyManagementMode: mode,
                            sizingMethod:
                              mode === "turtle"
                                ? "risk_based"
                                : current.sizingMethod,
                            // Prefill only from the default the strategy
                            // declared for this very mode, and only the first
                            // time. Refilling would discard what was typed the
                            // moment the operator looked at another mode.
                            deployedMoneyManagement:
                              isBuiltInMoneyManagement(mode) ||
                              declared.mode !== mode ||
                              current.deployedMoneyManagement[mode] !== undefined
                                ? current.deployedMoneyManagement
                                : {
                                    ...current.deployedMoneyManagement,
                                    [mode]: settingsJson(declared),
                                  },
                          }));
                        }}
                      >
                        {!form.moneyManagementMode && (
                          <option value="" disabled>
                            자금 관리 정책을 선택하세요
                          </option>
                        )}
                        {moneyManagementSelectionInvalid && (
                          <option value={form.moneyManagementMode} disabled>
                            {form.moneyManagementMode} · 더 이상 지원되지 않음
                          </option>
                        )}
                        {supportedMoneyManagement.map((mode) => (
                          <option key={mode} value={mode}>
                            {moneyManagementLabel(mode)}
                          </option>
                        ))}
                      </select>
                    </Label>
                  ) : (
                    <p className="rounded border bg-background/40 p-2 text-xs">
                      {moneyManagementLabel(form.moneyManagementMode)}
                    </p>
                  )}
                  {form.moneyManagementMode === "manual" ? (
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Label>
                        레버리지
                        <GuidedInput
                          aria-label="수동 레버리지"
                          hint="자연수 · 1–100"
                          type="number"
                          min={1}
                          max={100}
                          step={1}
                          value={form.manualLeverage}
                          onChange={(event) =>
                            update("manualLeverage", event.target.value)
                          }
                          required
                        />
                      </Label>
                      <Label>
                        손익비
                        <GuidedInput
                          aria-label="수동 reward_risk"
                          hint="소수 가능 · 0.1–10 (2 = 손절폭의 2배를 목표)"
                          type="number"
                          min={0.1}
                          max={10}
                          step="any"
                          value={form.manualRewardRisk}
                          onChange={(event) =>
                            update("manualRewardRisk", event.target.value)
                          }
                          required
                        />
                      </Label>
                      <Label>
                        ATR 손절 배수
                        <GuidedInput
                          aria-label="수동 atr_stop_multiple"
                          hint="소수 가능 · 0.1–10 (2 = ATR의 2배를 손절폭)"
                          type="number"
                          min={0.1}
                          max={10}
                          step="any"
                          value={form.manualAtrStopMultiple}
                          onChange={(event) =>
                            update(
                              "manualAtrStopMultiple",
                              event.target.value,
                            )
                          }
                          required
                        />
                      </Label>
                    </div>
                  ) : form.moneyManagementMode === "turtle" ? (
                    <div className="rounded-lg border bg-background/40 p-3 text-xs">
                      <p className="font-medium text-teal-100">
                        확정 일봉 N으로 거래당 위험 1% 이내 자동 계산
                      </p>
                      <p className="mt-1 leading-relaxed text-muted-foreground">
                        고정 목표가는 만들지 않고 전략의 청산 판단을 사용합니다.
                        현재 진행 중인 일봉은 N 계산에서 제외합니다.
                      </p>
                      <details className="mt-3">
                        <summary className="cursor-pointer text-muted-foreground">
                          Turtle 고급값
                        </summary>
                        <div className="mt-3 grid gap-3 sm:grid-cols-3">
                          <Label>
                            N 기간 (1d)
                            <GuidedInput
                              aria-label="Turtle N 기간"
                              hint="자연수 · 2–200 (일봉 개수)"
                              type="number"
                              min={2}
                              max={200}
                              step={1}
                              value={form.turtleNPeriod}
                              onChange={(event) =>
                                update("turtleNPeriod", event.target.value)
                              }
                              required
                            />
                          </Label>
                          <Label>
                            손절 N 배수
                            <GuidedInput
                              aria-label="Turtle 손절 N 배수"
                              hint="소수 가능 · 0.1–10 (2 = N의 2배를 손절폭)"
                              type="number"
                              min={0.1}
                              max={10}
                              step="any"
                              value={form.turtleStopNMultiple}
                              onChange={(event) =>
                                update(
                                  "turtleStopNMultiple",
                                  event.target.value,
                                )
                              }
                              required
                            />
                          </Label>
                          <Label>
                            레버리지 상한
                            <GuidedInput
                              aria-label="Turtle 레버리지 상한"
                              hint="자연수 · 1–100"
                              type="number"
                              min={1}
                              max={100}
                              step={1}
                              value={form.turtleLeverageCap}
                              onChange={(event) =>
                                update(
                                  "turtleLeverageCap",
                                  event.target.value,
                                )
                              }
                              required
                            />
                          </Label>
                        </div>
                      </details>
                    </div>
                  ) : (
                    <div className="grid gap-2 rounded-lg border bg-background/40 p-3 text-xs">
                      <p className="font-medium text-teal-100">
                        {form.moneyManagementMode} 정책 설정
                      </p>
                      <p className="leading-relaxed text-muted-foreground">
                        이 정책은 파일로 배포되어 이 화면에 전용 입력란이 없습니다.
                        설정을 JSON으로 적으면 서버가 그 정책의 정의로 검증합니다.
                        비워 두면 정책의 기본값이 쓰입니다.
                      </p>
                      <label
                        htmlFor="deployed-money-management"
                        className="grid gap-1.5 font-medium"
                      >
                        자금 관리 설정 JSON
                        <textarea
                          id="deployed-money-management"
                          aria-label="배포 정책 설정"
                          className={textareaClass}
                          value={
                            form.deployedMoneyManagement[
                              form.moneyManagementMode
                            ] ?? ""
                          }
                          onChange={(event) =>
                            update("deployedMoneyManagement", {
                              ...form.deployedMoneyManagement,
                              [form.moneyManagementMode]: event.target.value,
                            })
                          }
                          spellCheck={false}
                        />
                      </label>
                    </div>
                  )}
                  </div>
                ) : selectedStrategy ? (
                  <div className="rounded-lg border border-teal-500/20 bg-teal-500/5 p-4 text-xs text-muted-foreground md:col-span-2">
                    이 전략은 자금 관리 정책을 사용하지 않습니다. 실행 설정에도 자금 관리를 담지 않습니다.
                  </div>
                ) : null}
              </section>

              <section className="grid gap-4 border-t pt-5 sm:grid-cols-2">
                <Label className="sm:col-span-2">
                  심볼
                  <GuidedInput
                    aria-label="심볼"
                    value={form.symbol}
                    hint="BASE/QUOTE 또는 BASE/QUOTE:SETTLE 형식 (예: BTC/USDT:USDT)"
                    pattern="^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$"
                    title="BASE/QUOTE 또는 BASE/QUOTE:SETTLE 형식으로 입력 가능합니다."
                    onChange={(event) => update("symbol", event.target.value)}
                    required
                  />
                </Label>
                {selectedStrategy &&
                  (selectedStrategy.supported_timeframes.length > 1 ||
                    timeframeSelectionInvalid) && (
                    <Label className="sm:col-span-2">
                      타임프레임
                      <select
                        className={selectClass}
                        value={form.timeframe}
                        onChange={(event) =>
                          update("timeframe", event.target.value)
                        }
                      >
                        {timeframeSelectionInvalid && (
                          <option value={form.timeframe} disabled>
                            {form.timeframe} · 더 이상 지원되지 않음
                          </option>
                        )}
                        {selectedStrategy.supported_timeframes.map((timeframe) => (
                          <option key={timeframe} value={timeframe}>
                            {timeframe}
                          </option>
                        ))}
                      </select>
                    </Label>
                  )}
                <Label>
                  시작 (KST)
                  <DateTimePickerField
                    value={form.start}
                    onChange={(value) => update("start", value)}
                    aria-label="시작 (KST)"
                  />
                  <span className="mt-1 block text-[10px] font-normal leading-relaxed text-muted-foreground">
                    달력에서 선택 · 한국 시간 · 분 단위
                  </span>
                </Label>
                <Label>
                  종료 (KST)
                  <DateTimePickerField
                    value={form.end}
                    onChange={(value) => update("end", value)}
                    aria-label="종료 (KST)"
                  />
                  <span className="mt-1 block text-[10px] font-normal leading-relaxed text-muted-foreground">
                    시작보다 뒤여야 하며, 아래 보유 구간 안이어야 합니다
                  </span>
                </Label>
                <div
                  className={cn(
                    "sm:col-span-2 rounded-lg border p-3 text-xs",
                    coverageWarning
                      ? "border-amber-500/25 bg-amber-500/10 text-amber-200"
                      : "bg-muted/20 text-muted-foreground",
                  )}
                >
                  <div className="flex items-center gap-2">
                    {coverage.isFetching && (
                      <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                    )}
                    {coverageWarning && <AlertTriangle className="h-3.5 w-3.5" />}
                    <span className="font-medium">데이터 커버리지</span>
                  </div>
                  {coverage.data ? (
                    <p className="mt-1">
                      {coverage.data.available_from && coverage.data.available_to
                        ? `${formatTimestamp(coverage.data.available_from)} → ${formatTimestamp(
                            coverage.data.available_to,
                          )}`
                        : "가용 행 없음"}
                      {" · "}1m {coverage.data.row_count.toLocaleString()}행
                      {" · "}누락 추정{" "}
                      {coverage.data.missing_1m_rows.toLocaleString()}행
                    </p>
                  ) : coverage.isError ? (
                    <p className="mt-1 text-red-300">{coverage.error.message}</p>
                  ) : (
                    <p className="mt-1">가용 구간을 조회하고 있습니다.</p>
                  )}
                  {coverageWarning && <p className="mt-1 font-medium">{coverageWarning}</p>}
                </div>
                <div className="sm:col-span-2 rounded-lg border border-teal-500/20 bg-teal-500/5 p-3 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium text-teal-100">자동 설정</p>
                    <Badge variant="outline">제출 payload에 기록</Badge>
                  </div>
                  <dl className="mt-2 grid gap-x-4 gap-y-1 text-muted-foreground sm:grid-cols-2">
                    <div>
                      <dt className="inline">실행 이름 </dt>
                      <dd className="inline font-mono text-foreground">
                        {automaticRunName(form.strategyId, form.symbol)}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline">타임프레임 </dt>
                      <dd className="inline text-foreground">{form.timeframe}</dd>
                    </div>
                    <div>
                      <dt className="inline">거래소·마켓 </dt>
                      <dd className="inline text-foreground">
                        Binance · {form.marketType === "futures" ? "선물" : "현물"}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline">데이터셋 </dt>
                      <dd className="inline font-mono text-foreground">
                        {form.dataSource}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="inline">지표·체결 </dt>
                      <dd className="inline text-foreground">
                        전략 자동 지표 · 다음 봉 체결
                      </dd>
                    </div>
                  </dl>
                </div>
              </section>

              <details className="group border-t pt-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg border bg-muted/15 px-4 py-3">
                  <span>
                    <span className="block text-sm font-semibold">고급 실행 가정</span>
                    <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                      자본·포지션 크기·수수료는 기본값을 사용합니다.
                    </span>
                  </span>
                  <span className="text-xs text-muted-foreground group-open:hidden">
                    펼치기
                  </span>
                  <span className="hidden text-xs text-muted-foreground group-open:inline">
                    접기
                  </span>
                </summary>
                <div className="mt-4 grid gap-4 rounded-lg border bg-muted/10 p-4 sm:grid-cols-2">
                  <Label>
                    초기 자본
                    <GuidedInput
                      aria-label="초기 자본"
                      hint="0보다 큰 금액 · 소수 가능"
                      type="number"
                      min={POSITIVE_NUMBER_INPUT_MIN}
                      step="any"
                      value={form.initialCapital}
                      onChange={(event) =>
                        update("initialCapital", event.target.value)
                      }
                      required
                    />
                  </Label>
                  {form.moneyManagementMode === "turtle" ? (
                    <div className="rounded-lg border bg-background/40 p-3 text-xs">
                      <p className="font-medium">사이징 · 자동</p>
                      <p className="mt-1 text-muted-foreground">
                        Turtle 정책은 전역 거래당 리스크 상한을 사용합니다.
                      </p>
                    </div>
                  ) : (
                    <Label>
                      사이징
                      <select
                        className={selectClass}
                        value={form.sizingMethod}
                        onChange={(event) =>
                          update(
                            "sizingMethod",
                            event.target.value as SizingMethod,
                          )
                        }
                      >
                        <option value="risk_based">리스크 기준</option>
                        <option value="pct">자본 비율</option>
                      </select>
                    </Label>
                  )}
                  {form.sizingMethod === "risk_based" ? (
                    <Label>
                      거래당 리스크 (0 &lt; x ≤ 0.01)
                      <GuidedInput
                        aria-label="risk_per_trade"
                        hint="0 초과 0.01 이하 · 소수 (0.01 = 자본의 1%)"
                        type="number"
                        inputMode="decimal"
                        min={POSITIVE_NUMBER_INPUT_MIN}
                        max={0.01}
                        step="any"
                        value={form.riskPerTrade}
                        onChange={(event) =>
                          update("riskPerTrade", event.target.value)
                        }
                        required
                      />
                    </Label>
                  ) : (
                    <Label>
                      포지션 자본 비율 (0 &lt; x ≤ 1)
                      <GuidedInput
                        aria-label="position_size_pct"
                        hint="0 초과 1 이하 · 소수 (0.5 = 자본의 50%)"
                        type="number"
                        inputMode="decimal"
                        min={POSITIVE_NUMBER_INPUT_MIN}
                        max={1}
                        step="any"
                        value={form.positionSizePct}
                        onChange={(event) =>
                          update("positionSizePct", event.target.value)
                        }
                        required
                      />
                    </Label>
                  )}
                  <div className="hidden sm:block" aria-hidden="true" />
                  <Label>
                    선물 taker 수수료율
                    <GuidedInput
                      aria-label="선물 taker 수수료율"
                      hint="0 이상 소수 · 비율 (0.0004 = 0.04%)"
                      type="number"
                      min={0}
                      step="any"
                      value={form.futuresTakerFeeRate}
                      onChange={(event) =>
                        update("futuresTakerFeeRate", event.target.value)
                      }
                    />
                  </Label>
                  <Label>
                    진입 슬리피지율
                    <GuidedInput
                      aria-label="진입 슬리피지율"
                      hint="0 이상 소수 · 비율 (0.0005 = 0.05%)"
                      type="number"
                      min={0}
                      step="any"
                      value={form.futuresEntrySlippageRate}
                      onChange={(event) =>
                        update("futuresEntrySlippageRate", event.target.value)
                      }
                    />
                  </Label>
                  <Label>
                    청산 슬리피지율
                    <GuidedInput
                      aria-label="청산 슬리피지율"
                      hint="0 이상 소수 · 비율 (0.0001 = 0.01%)"
                      type="number"
                      min={0}
                      step="any"
                      value={form.exitSlippageRate}
                      onChange={(event) =>
                        update("exitSlippageRate", event.target.value)
                      }
                    />
                  </Label>
                  <Label>
                    펀딩비 대체율
                    <GuidedInput
                      aria-label="펀딩비 대체율"
                      hint="0 이상 소수 · 8시간당 비율 (0.0001 = 0.01%)"
                      type="number"
                      min={0}
                      step="any"
                      value={form.fundingFallbackRate}
                      onChange={(event) =>
                        update("fundingFallbackRate", event.target.value)
                      }
                    />
                  </Label>
                  <p className="text-xs leading-relaxed text-muted-foreground sm:col-span-2">
                    시드 0 · 프로필 {selectedStrategy?.profile_id ?? "없음"} · 지표 자동 선택 · tf_candle
                    신호를 다음 봉에 체결
                  </p>
                </div>
              </details>

              <div className="relative border-t pt-5">
                <details>
                  <summary className="cursor-pointer pr-32 text-sm font-semibold">
                    연구 가설 (선택)
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      가설·주지표를 제출 payload에 포함
                    </span>
                  </summary>
                  <div className="mt-4">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={form.preregEnabled}
                      onChange={(event) =>
                        update("preregEnabled", event.target.checked)
                      }
                      className="h-4 w-4 accent-teal-500"
                    />
                    실행 제출 메타데이터 사용
                  </label>
                  <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-xs text-amber-100">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <p>
                      사전등록 잠금은 쓰기 엔드포인트 미구현으로 유보(3차)되었습니다.
                      아래 값은 현재 실행 제출에만 포함되며 초안 저장·잠금·불변성을
                      보장하지 않습니다.
                    </p>
                  </div>
                  {form.preregEnabled && (
                    <div className="mt-4 grid gap-4 rounded-lg border bg-muted/20 p-4 sm:grid-cols-2">
                    <Label className="sm:col-span-2">
                      가설
                      <GuidedInput
                        aria-label="가설"
                        hint="문장으로 자유롭게 입력"
                        value={form.hypothesis}
                        onChange={(event) => update("hypothesis", event.target.value)}
                      />
                    </Label>
                    <Label>
                      주지표
                      <select
                        className={selectClass}
                        value={form.primaryMetric}
                        onChange={(event) =>
                          update("primaryMetric", event.target.value as PrimaryMetric)
                        }
                      >
                        {[
                          "pf",
                          "sortino",
                          "calmar_or_mar",
                          "sqn",
                          "mdd",
                          "ror",
                          "sharpe",
                          "win_rate",
                          "payoff",
                          "expectancy_r",
                          "ulcer",
                          "kelly",
                          "trade_count",
                        ].map((metric) => (
                          <option key={metric} value={metric}>
                            {metric}
                          </option>
                        ))}
                      </select>
                    </Label>
                    <Label>
                      선언자
                      <GuidedInput
                        aria-label="선언자"
                        hint="이름 또는 팀 이름"
                        value={form.declaredBy}
                        onChange={(event) => update("declaredBy", event.target.value)}
                      />
                    </Label>
                    <Label>
                      성공 기준
                      <GuidedInput
                        aria-label="성공 기준"
                        hint="숫자 · 소수 가능 (주지표와 같은 단위)"
                        type="number"
                        step="any"
                        value={form.successThreshold}
                        onChange={(event) =>
                          update("successThreshold", event.target.value)
                        }
                      />
                    </Label>
                    <Label>
                      실패 기준
                      <GuidedInput
                        aria-label="실패 기준"
                        hint="숫자 · 소수 가능 (주지표와 같은 단위)"
                        type="number"
                        step="any"
                        value={form.failureThreshold}
                        onChange={(event) =>
                          update("failureThreshold", event.target.value)
                        }
                      />
                    </Label>
                    <label className="flex items-center gap-2 text-xs font-medium sm:col-span-2">
                      <input
                        type="checkbox"
                        checked={form.higherIsBetter}
                        onChange={(event) =>
                          update("higherIsBetter", event.target.checked)
                        }
                        className="h-4 w-4 accent-teal-500"
                      />
                      높을수록 좋음
                    </label>
                    </div>
                  )}
                  </div>
                </details>
                <div className="absolute right-0 top-4">
                  <ResearchHelpDialog helpId="preregistration" />
                </div>
              </div>

              <details className="border-t pt-5" open={sweepEnabled}>
                <summary className="cursor-pointer text-sm font-semibold">
                  스윕 설정
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    {sweepEnabled
                      ? `켜짐 · ${sweepType}${
                          sweepType === "grid"
                            ? gridSweepBlocked
                              ? " · 유효한 축 필요"
                              : ` · 축 ${axisTwoEnabled ? 2 : 1}개`
                            : ""
                        }`
                      : "꺼짐 · 단일 백테스트로 실행됩니다."}
                  </span>
                </summary>
                <section className="mt-4">
                  <label
                    className="mb-4 flex items-start gap-2 rounded-lg border bg-background/40 p-3 text-sm"
                    htmlFor="sweep-enabled"
                  >
                    <input
                      id="sweep-enabled"
                      type="checkbox"
                      className="mt-0.5 h-4 w-4"
                      checked={sweepEnabled}
                      onChange={(event) => setSweepEnabled(event.target.checked)}
                    />
                    <span>
                      <span className="font-medium">스윕으로 실행</span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        켜면 아래 설정으로 여러 실행을 만들고, 끄면 아래 설정을 무시하고
                        단일 백테스트 하나만 실행합니다.
                      </span>
                    </span>
                  </label>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold">스윕 빌더</p>
                        <ResearchHelpDialog helpId="sweep" />
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        위 기준 RunConfig와 인라인 사전등록을 그대로 재사용합니다.
                      </p>
                    </div>
                    <Badge variant="outline">BATCH DRY-RUN</Badge>
                  </div>
                  <div className="mt-4 grid gap-4 rounded-lg border bg-muted/15 p-4 sm:grid-cols-2">
                  <Label>
                    유형
                    <select
                      className={selectClass}
                      value={sweepType}
                      aria-invalid={gridSweepBlocked || undefined}
                      onChange={(event) =>
                        setSweepType(event.target.value as SweepType)
                      }
                    >
                      <option value="grid">grid</option>
                      <option value="walk_forward">walk_forward</option>
                      <option value="is_oos">is_oos</option>
                    </select>
                  </Label>
                  {sweepType === "walk_forward" && (
                    <Label>
                      folds (2–20)
                      <GuidedInput
                        aria-label="folds"
                        hint="자연수 · 2–20"
                        type="number"
                        min={2}
                        max={20}
                        step={1}
                        value={folds}
                        onChange={(event) => setFolds(event.target.value)}
                      />
                    </Label>
                  )}
                  {sweepType === "is_oos" && (
                    <Label>
                      <span className="flex items-center justify-between gap-2">
                        split (0–1)
                        <button
                          type="button"
                          className="font-normal text-teal-300 hover:underline"
                          onClick={() => {
                            setSplitCustomized(false);
                            setSplit(
                              alignedDefaultSplit(
                                form.start,
                                form.end,
                                form.timeframe,
                              ),
                            );
                          }}
                        >
                          timeframe 자동정렬
                        </button>
                      </span>
                      <GuidedInput
                        aria-label="split"
                        hint="0 초과 1 미만 소수 (0.7 = 앞 70%를 인샘플)"
                        type="number"
                        min={POSITIVE_NUMBER_INPUT_MIN}
                        max={SPLIT_INPUT_MAX}
                        step="any"
                        value={split}
                        onChange={(event) => {
                          setSplitCustomized(true);
                          setSplit(event.target.value);
                        }}
                      />
                    </Label>
                  )}
                  {sweepType === "grid" && (
                    <>
                      <div className="grid gap-3 rounded-md border p-3 sm:col-span-2 sm:grid-cols-2">
                        <Label>
                          축 1 파라미터
                          {axisCandidates.length > 0 ? (
                            <select
                              className={selectClass}
                              value={axisOneParameter}
                              onChange={(event) =>
                                setAxisOneParameter(event.target.value)
                              }
                            >
                              {axisCandidates.map((candidate) => (
                                <option key={candidate} value={candidate}>
                                  {candidate}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <GuidedInput
                              aria-label="축 1 파라미터"
                              hint="파라미터 이름 (자금 관리는 money_management. 접두어)"
                              value={axisOneParameter}
                              onChange={(event) =>
                                setAxisOneParameter(event.target.value)
                              }
                              placeholder="reward_risk"
                            />
                          )}
                        </Label>
                        <Label>
                          축 1 값 JSON 배열
                          <GuidedInput
                            aria-label="축 1 값 JSON 배열"
                            hint={axisValuesHint(axisOneParameter)}
                            value={axisOneValues}
                            onChange={(event) => setAxisOneValues(event.target.value)}
                            placeholder="[1.5, 2.0, 2.5]"
                          />
                        </Label>
                      </div>
                      <label
                        className="flex items-center gap-2 text-xs font-medium sm:col-span-2"
                        htmlFor="sweep-axis-two"
                      >
                        <input
                          id="sweep-axis-two"
                          type="checkbox"
                          checked={axisTwoEnabled}
                          onChange={(event) => setAxisTwoEnabled(event.target.checked)}
                          className="h-4 w-4 accent-teal-500"
                        />
                        두 번째 히트맵 축
                      </label>
                      {axisTwoEnabled && (
                        <div className="grid gap-3 rounded-md border p-3 sm:col-span-2 sm:grid-cols-2">
                          <Label>
                            축 2 파라미터
                            {axisCandidates.length > 0 ? (
                              <select
                                className={selectClass}
                                value={axisTwoParameter}
                                onChange={(event) =>
                                  setAxisTwoParameter(event.target.value)
                                }
                              >
                                {axisCandidates
                                  .filter(
                                    (candidate) =>
                                      candidate !== axisOneParameter,
                                  )
                                  .map((candidate) => (
                                    <option key={candidate} value={candidate}>
                                      {candidate}
                                    </option>
                                  ))}
                              </select>
                            ) : (
                              <GuidedInput
                                aria-label="축 2 파라미터"
                                hint="축 1과 다른 파라미터 이름"
                                value={axisTwoParameter}
                                onChange={(event) =>
                                  setAxisTwoParameter(event.target.value)
                                }
                                placeholder="atr_stop_multiple"
                              />
                            )}
                          </Label>
                          <Label>
                            축 2 값 JSON 배열
                            <GuidedInput
                              aria-label="축 2 값 JSON 배열"
                              hint={axisValuesHint(axisTwoParameter)}
                              value={axisTwoValues}
                              onChange={(event) =>
                                setAxisTwoValues(event.target.value)
                              }
                              placeholder="[1.5, 2.0]"
                            />
                          </Label>
                        </div>
                      )}
                    </>
                  )}
                  </div>
                </section>
              </details>

              {notice && (
                <div
                  className={cn(
                    "rounded-lg border p-3 text-xs",
                    "whitespace-pre-line",
                    notice.kind === "success"
                      ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-200"
                      : "border-red-500/20 bg-red-500/5 text-red-200",
                  )}
                >
                  {notice.message}
                </div>
              )}

              {!runReadiness.runnable && runReadiness.reason && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
                  {runReadiness.reason}
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-5">
                <p className="max-w-xl text-[11px] leading-relaxed text-muted-foreground">
                  같은 설정을 다시 트리거해도 매번 새 run이 생성됩니다. config_hash
                  미리보기와 중복 차단은 이 단계에 포함되지 않습니다.
                </p>
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    disabled={
                      busy !== null ||
                      Boolean(coverageWarning) ||
                      !runReadiness.runnable ||
                      gridSweepBlocked
                    }
                    title={
                      !runReadiness.runnable
                        ? runReadiness.reason ?? undefined
                        : coverageWarning
                          ? "데이터 커버리지 경고를 해소한 뒤 실행하세요."
                          : gridSweepBlocked
                            ? "grid 스윕에는 유효한 축을 하나 이상 입력하세요."
                            : undefined
                    }
                  >
                    {busy !== null ? (
                      <LoaderCircle className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : sweepEnabled ? (
                      <FlaskConical className="mr-1.5 h-4 w-4" />
                    ) : (
                      <Play className="mr-1.5 h-4 w-4" />
                    )}
                    {!runReadiness.runnable
                      ? "실행할 수 없음"
                      : gridSweepBlocked
                        ? "grid 축을 입력하세요"
                        : sweepEnabled
                          ? "스윕 실행"
                          : "백테스트 실행"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </form>

        <Card className="xl:sticky xl:top-20">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>실행 큐</CardTitle>
                <CardDescription>SSE 상태 스트림 · 현재 브라우저 세션</CardDescription>
              </div>
              <Badge variant="secondary">{jobs.length + sweeps.length} jobs</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="max-h-[calc(100vh-12rem)] space-y-3 overflow-y-auto pr-1 scrollbar-thin">
              {jobs.length === 0 && sweeps.length === 0 ? (
                <div className="rounded-lg border border-dashed p-8 text-center">
                  <Clock3 className="mx-auto h-6 w-6 text-muted-foreground/60" />
                  <p className="mt-3 text-sm font-medium">추적 중인 실행이 없습니다</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    트리거가 수락되면 QUEUED부터 종단 상태까지 표시합니다.
                  </p>
                </div>
              ) : (
                <>
                  {sweeps.map((sweep) => (
                    <SweepJobRow
                      key={sweep.accepted.job_id}
                      sweep={sweep}
                      onSelectResult={openSweepResult}
                    />
                  ))}
                  {jobs.map((job) => (
                    <JobRow
                      key={job.accepted.job_id}
                      job={job}
                      onEdit={loadSubmission}
                    />
                  ))}
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>저장된 스윕 결과 열기</CardTitle>
          <CardDescription>
            현재 세션 밖에서 생성된 결과도 sweep_id로 조회하며 선택은 URL에 보존됩니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              openSweepResult(sweepLookup);
            }}
          >
            <GuidedInput
              aria-label="스윕 ID"
              hint="조회할 스윕의 식별자"
              value={sweepLookup}
              onChange={(event) => setSweepLookup(event.target.value)}
              placeholder="sweep_id"
              required
            />
            {sweeps.some((sweep) => sweep.status.sweep_id) && (
              <select
                aria-label="현재 세션 스윕 선택"
                value={selectedSweepId ?? ""}
                onChange={(event) => {
                  setSweepLookup(event.target.value);
                  openSweepResult(event.target.value);
                }}
                className={selectClass}
              >
                <option value="" disabled>
                  현재 세션에서 선택
                </option>
                {sweeps.flatMap((sweep) =>
                  sweep.status.sweep_id
                    ? [
                        <option key={sweep.status.sweep_id} value={sweep.status.sweep_id}>
                          {sweep.submission.config.run_name} · {sweep.status.sweep_id}
                        </option>,
                      ]
                    : [],
                )}
              </select>
            )}
            <Button type="submit" variant="outline">
              결과 열기
            </Button>
          </form>
        </CardContent>
      </Card>
      <SweepResults
        sweep={
          sweeps.find((sweep) => sweep.status.sweep_id === selectedSweepId) ??
          (selectedSweepId ? undefined : sweeps[0])
        }
        sweepId={selectedSweepId}
      />
    </div>
  );
}

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
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "wouter";

import {
  apiClient,
  requestErrorMessage,
  type JobStatus,
  type PreregistrationInput,
  type RunConfigInput,
  type RunSubmission,
} from "../api/client";
import { Badge, type BadgeProps } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Input } from "../components/ui/input";
import { useRunJobs, type TrackedJob } from "../contexts/run-jobs";
import { cn, formatTimestamp, shortHash } from "../lib/utils";

type PrimaryMetric = NonNullable<PreregistrationInput["primary_metric"]>;
type SizingMethod = NonNullable<RunConfigInput["sizing_method"]>;
type IndicatorMode = NonNullable<RunConfigInput["indicator_mode"]>;
type MarketType = RunConfigInput["market_type"];

interface FormState {
  runName: string;
  strategyId: string;
  params: string;
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
  runName: "p2a-dry-run",
  strategyId: "vessel-reference",
  params: "{}",
  symbol: "BTC/USDT:USDT",
  exchange: "binance",
  timeframe: "1h",
  marketType: "futures",
  dataSource: "crypto_data.ohlcv_futures",
  start: "2025-07-01T00:00",
  end: "2025-07-04T00:00",
  initialCapital: "10000",
  seed: "976",
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

function utcIso(value: string, label: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error(`${label} 시간이 올바르지 않습니다.`);
  return date.toISOString();
}

function localDateTime(value: string): string {
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function optionalNumber(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`숫자 값 '${value}'이 올바르지 않습니다.`);
  return parsed;
}

function buildSubmission(form: FormState): RunSubmission {
  const config: RunSubmission["config"] = {
    run_name: form.runName.trim(),
    strategy_id: form.strategyId,
    params: parseObject(form.params, "전략 파라미터"),
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
    profile_ref: form.profileRef.trim(),
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

function JobRow({
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
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-2/3 animate-pulse rounded-full bg-teal-400/80" />
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

export function RunManagementPage() {
  const { jobs, track } = useRunJobs();
  const [form, setForm] = useState<FormState>(initialForm);
  const [busy, setBusy] = useState<"validate" | "trigger" | null>(null);
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);

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

  useEffect(() => {
    if (!selectedStrategy || form.params !== "{}") return;
    setForm((current) => ({
      ...current,
      params: JSON.stringify(selectedStrategy.default_params, null, 2),
      timeframe: selectedStrategy.supported_timeframes[0] ?? current.timeframe,
    }));
  }, [form.params, selectedStrategy]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function validateConfig(event: FormEvent) {
    event.preventDefault();
    setBusy("validate");
    setNotice(null);
    try {
      const submission = buildSubmission(form);
      const { data, error } = await apiClient.POST("/api/v1/run-config:validate", {
        body: submission.config,
      });
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("검증 응답이 비어 있습니다.");
      setNotice({
        kind: "success",
        message: `설정 검증 완료 · UTC ${data.start} → ${data.end}`,
      });
    } catch (error) {
      setNotice({
        kind: "error",
        message: error instanceof Error ? error.message : "설정을 검증하지 못했습니다.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function triggerRun() {
    setBusy("trigger");
    setNotice(null);
    try {
      const submission = buildSubmission(form);
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

  function loadSubmission(submission: RunSubmission) {
    const config = submission.config;
    const prereg = submission.prereg;
    setForm((current) => ({
      ...current,
      runName: config.run_name,
      strategyId: config.strategy_id,
      params: JSON.stringify(config.params ?? {}, null, 2),
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
      positionSizePct: String(config.position_size_pct ?? current.positionSizePct),
      futuresTakerFeeRate: String(
        config.cost_values?.futures_taker_fee_rate ?? current.futuresTakerFeeRate,
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
      explicitIndicators: JSON.stringify(config.explicit_indicators ?? [], null, 2),
      profileRef: config.profile_ref,
      preregEnabled: Boolean(prereg),
      hypothesis: prereg?.hypothesis ?? "",
      primaryMetric: prereg?.primary_metric ?? "pf",
      successThreshold: String(prereg?.success_threshold ?? ""),
      failureThreshold: String(prereg?.failure_threshold ?? ""),
      higherIsBetter: prereg?.higher_is_better ?? true,
      declaredBy: prereg?.declared_by ?? "",
    }));
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
        <form onSubmit={validateConfig}>
          <Card>
            <CardHeader>
              <CardTitle>새 백테스트 트리거</CardTitle>
              <CardDescription>
                모든 금액·비용 값은 Decimal 문자열로 전송되며 서버 RunConfig가 최종
                검증합니다.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <section className="grid gap-4 md:grid-cols-2">
                <Label>
                  <span className="flex items-center justify-between gap-2">
                    실행 이름
                    <span className="font-normal text-muted-foreground">
                      24자 이하 소문자 kebab-case
                    </span>
                  </span>
                  <Input
                    value={form.runName}
                    maxLength={24}
                    pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
                    title="24자 이하 소문자 kebab-case로 입력하세요."
                    onChange={(event) => update("runName", event.target.value)}
                    required
                  />
                </Label>
                <Label>
                  전략
                  <select
                    className={selectClass}
                    value={form.strategyId}
                    onChange={(event) => {
                      update("strategyId", event.target.value);
                      update("params", "{}");
                    }}
                    disabled={strategies.isLoading}
                  >
                    {(strategies.data ?? []).map((strategy) => (
                      <option key={strategy.strategy_id} value={strategy.strategy_id}>
                        {strategy.display_name} · {strategy.strategy_version}
                      </option>
                    ))}
                    {!strategies.data?.length && (
                      <option value={form.strategyId}>{form.strategyId}</option>
                    )}
                  </select>
                </Label>
                {selectedStrategy && (
                  <div className="md:col-span-2 rounded-lg border bg-muted/25 p-3 text-xs text-muted-foreground">
                    <span className="text-foreground">
                      지원 {selectedStrategy.supported_timeframes.join(", ")}
                    </span>
                    {" · "}최소 이력 {selectedStrategy.min_history}
                    {" · "}필수 지표{" "}
                    {selectedStrategy.required_indicators
                      .map((item) => String(item.name ?? "unknown"))
                      .join(", ")}
                    {" · "}출처 {selectedStrategy.source}
                  </div>
                )}
                <Label className="md:col-span-2">
                  전략 파라미터 JSON
                  <textarea
                    className={textareaClass}
                    value={form.params}
                    onChange={(event) => update("params", event.target.value)}
                    spellCheck={false}
                  />
                </Label>
              </section>

              <section className="grid gap-4 border-t pt-5 sm:grid-cols-2 lg:grid-cols-4">
                <Label className="sm:col-span-2">
                  심볼
                  <Input
                    value={form.symbol}
                    onChange={(event) => update("symbol", event.target.value)}
                    required
                  />
                </Label>
                <Label>
                  거래소
                  <Input
                    value={form.exchange}
                    onChange={(event) => update("exchange", event.target.value)}
                    required
                  />
                </Label>
                <Label>
                  마켓
                  <select
                    className={selectClass}
                    value={form.marketType}
                    onChange={(event) =>
                      update("marketType", event.target.value as MarketType)
                    }
                  >
                    <option value="futures">futures</option>
                    <option value="spot">spot</option>
                  </select>
                </Label>
                <Label>
                  타임프레임
                  <Input
                    value={form.timeframe}
                    pattern="^[1-9][0-9]*[mhd]$"
                    onChange={(event) => update("timeframe", event.target.value)}
                    required
                  />
                </Label>
                <Label className="sm:col-span-2 lg:col-span-3">
                  데이터 소스
                  <Input
                    value={form.dataSource}
                    onChange={(event) => update("dataSource", event.target.value)}
                    required
                  />
                </Label>
                <Label className="sm:col-span-2">
                  시작 (브라우저 로컬 시간)
                  <Input
                    type="datetime-local"
                    value={form.start}
                    onChange={(event) => update("start", event.target.value)}
                    required
                  />
                </Label>
                <Label className="sm:col-span-2">
                  종료 (브라우저 로컬 시간)
                  <Input
                    type="datetime-local"
                    value={form.end}
                    onChange={(event) => update("end", event.target.value)}
                    required
                  />
                </Label>
              </section>

              <section className="grid gap-4 border-t pt-5 sm:grid-cols-2 lg:grid-cols-4">
                <Label className="sm:col-span-2">
                  초기 자본 (Decimal)
                  <Input
                    inputMode="decimal"
                    value={form.initialCapital}
                    onChange={(event) => update("initialCapital", event.target.value)}
                    required
                  />
                </Label>
                <Label>
                  시드
                  <Input
                    type="number"
                    step="1"
                    value={form.seed}
                    onChange={(event) => update("seed", event.target.value)}
                    required
                  />
                </Label>
                <Label>
                  사이징
                  <select
                    className={selectClass}
                    value={form.sizingMethod}
                    onChange={(event) =>
                      update("sizingMethod", event.target.value as SizingMethod)
                    }
                  >
                    <option value="risk_based">risk_based</option>
                    <option value="pct">pct</option>
                  </select>
                </Label>
                {form.sizingMethod === "risk_based" ? (
                  <Label className="sm:col-span-2">
                    risk_per_trade (0 &lt; x ≤ 0.01)
                    <Input
                      inputMode="decimal"
                      value={form.riskPerTrade}
                      onChange={(event) => update("riskPerTrade", event.target.value)}
                      required
                    />
                  </Label>
                ) : (
                  <Label className="sm:col-span-2">
                    position_size_pct (0 &lt; x ≤ 1)
                    <Input
                      inputMode="decimal"
                      value={form.positionSizePct}
                      onChange={(event) => update("positionSizePct", event.target.value)}
                      required
                    />
                  </Label>
                )}
                <Label className="sm:col-span-2">
                  프로필 참조
                  <Input
                    value={form.profileRef}
                    onChange={(event) => update("profileRef", event.target.value)}
                    required
                  />
                </Label>
              </section>

              <section className="grid gap-4 border-t pt-5 sm:grid-cols-2">
                <Label>
                  futures_taker_fee_rate
                  <Input
                    inputMode="decimal"
                    value={form.futuresTakerFeeRate}
                    onChange={(event) =>
                      update("futuresTakerFeeRate", event.target.value)
                    }
                  />
                </Label>
                <Label>
                  futures_entry_slippage_rate
                  <Input
                    inputMode="decimal"
                    value={form.futuresEntrySlippageRate}
                    onChange={(event) =>
                      update("futuresEntrySlippageRate", event.target.value)
                    }
                  />
                </Label>
                <Label>
                  exit_slippage_rate
                  <Input
                    inputMode="decimal"
                    value={form.exitSlippageRate}
                    onChange={(event) => update("exitSlippageRate", event.target.value)}
                  />
                </Label>
                <Label>
                  funding_fallback_rate
                  <Input
                    inputMode="decimal"
                    value={form.fundingFallbackRate}
                    onChange={(event) =>
                      update("fundingFallbackRate", event.target.value)
                    }
                  />
                </Label>
              </section>

              <section className="grid gap-4 border-t pt-5 sm:grid-cols-2">
                <Label>
                  지표 모드
                  <select
                    className={selectClass}
                    value={form.indicatorMode}
                    onChange={(event) =>
                      update("indicatorMode", event.target.value as IndicatorMode)
                    }
                  >
                    <option value="auto">auto</option>
                    <option value="explicit">explicit</option>
                    <option value="all">all</option>
                  </select>
                </Label>
                <div className="grid grid-cols-2 gap-3">
                  <Label>
                    trigger_feed
                    <Input value="tf_candle" disabled />
                  </Label>
                  <Label>
                    fill_timing
                    <Input value="next_bar" disabled />
                  </Label>
                </div>
                {form.indicatorMode === "explicit" && (
                  <Label className="sm:col-span-2">
                    명시 지표 JSON
                    <textarea
                      className={textareaClass}
                      value={form.explicitIndicators}
                      onChange={(event) =>
                        update("explicitIndicators", event.target.value)
                      }
                      spellCheck={false}
                    />
                  </Label>
                )}
              </section>

              <section className="border-t pt-5">
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    checked={form.preregEnabled}
                    onChange={(event) => update("preregEnabled", event.target.checked)}
                    className="h-4 w-4 accent-teal-500"
                  />
                  선택 사전등록
                  <span className="text-xs font-normal text-muted-foreground">
                    연구 규율상 가설·주지표 입력 권장
                  </span>
                </label>
                {form.preregEnabled && (
                  <div className="mt-4 grid gap-4 rounded-lg border bg-muted/20 p-4 sm:grid-cols-2">
                    <Label className="sm:col-span-2">
                      가설
                      <Input
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
                      <Input
                        value={form.declaredBy}
                        onChange={(event) => update("declaredBy", event.target.value)}
                      />
                    </Label>
                    <Label>
                      성공 기준
                      <Input
                        inputMode="decimal"
                        value={form.successThreshold}
                        onChange={(event) =>
                          update("successThreshold", event.target.value)
                        }
                      />
                    </Label>
                    <Label>
                      실패 기준
                      <Input
                        inputMode="decimal"
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
              </section>

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

              <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-5">
                <p className="max-w-xl text-[11px] leading-relaxed text-muted-foreground">
                  같은 설정을 다시 트리거해도 매번 새 run이 생성됩니다. config_hash
                  미리보기와 중복 차단은 이 단계에 포함되지 않습니다.
                </p>
                <div className="flex gap-2">
                  <Button type="submit" variant="outline" disabled={busy !== null}>
                    {busy === "validate" && (
                      <LoaderCircle className="mr-1.5 h-4 w-4 animate-spin" />
                    )}
                    설정 검증
                  </Button>
                  <Button
                    type="button"
                    onClick={() => void triggerRun()}
                    disabled={busy !== null}
                  >
                    {busy === "trigger" ? (
                      <LoaderCircle className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="mr-1.5 h-4 w-4" />
                    )}
                    트리거(모의)
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
              <Badge variant="secondary">{jobs.length} jobs</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="max-h-[calc(100vh-12rem)] space-y-3 overflow-y-auto pr-1 scrollbar-thin">
              {jobs.length === 0 ? (
                <div className="rounded-lg border border-dashed p-8 text-center">
                  <Clock3 className="mx-auto h-6 w-6 text-muted-foreground/60" />
                  <p className="mt-3 text-sm font-medium">추적 중인 실행이 없습니다</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    트리거가 수락되면 QUEUED부터 종단 상태까지 표시합니다.
                  </p>
                </div>
              ) : (
                jobs.map((job) => (
                  <JobRow key={job.accepted.job_id} job={job} onEdit={loadSubmission} />
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  LoaderCircle,
  Play,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  type FormEvent,
  useMemo,
  useState,
} from "react";

import {
  ApiRequestError,
  type DataJobRequest,
  type DataJobStatus,
  type InventoryItem,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Skeleton } from "../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  useDataJob,
  useDataJobs,
} from "../hooks/use-data-jobs";
import { useInventory } from "../hooks/use-inventory";
import { formatTimestamp } from "../lib/utils";

const DATA_SOURCE = "crypto_data.ohlcv_futures";
const MAX_RANGE_DAYS = 730;
const MAX_RANGE_MS = MAX_RANGE_DAYS * 24 * 60 * 60 * 1_000;
const symbolPattern =
  /^[A-Za-z0-9][A-Za-z0-9._-]*\/[A-Za-z0-9][A-Za-z0-9._-]*:[A-Za-z0-9][A-Za-z0-9._-]*$/;
const timeframeOptions = ["5m", "15m", "1h", "4h", "1d"] as const;

type DataJobOperation = DataJobRequest["operation"];
type AggregateTimeframe = (typeof timeframeOptions)[number];

interface DataJobForm {
  operation: DataJobOperation;
  symbol: string;
  start: string;
  end: string;
  timeframes: AggregateTimeframe[];
}

interface FormErrors {
  symbol?: string;
  start?: string;
  end?: string;
  timeframes?: string;
}

const coverageFormatter = new Intl.NumberFormat("ko-KR", {
  style: "percent",
  maximumFractionDigits: 2,
});

function period(item: InventoryItem) {
  if (!item.available_from || !item.available_to) return "데이터 없음";
  return `${formatTimestamp(item.available_from)} ~ ${formatTimestamp(item.available_to)}`;
}

function dateTimeLocalUtc(value: Date): string {
  return value.toISOString().slice(0, 16);
}

function initialForm(): DataJobForm {
  const end = new Date();
  end.setUTCSeconds(0, 0);
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1_000);
  return {
    operation: "backfill",
    symbol: "BTC/USDT:USDT",
    start: dateTimeLocalUtc(start),
    end: dateTimeLocalUtc(end),
    timeframes: [...timeframeOptions],
  };
}

function utcMilliseconds(value: string): number {
  return Date.parse(`${value}Z`);
}

function validateForm(form: DataJobForm): {
  errors: FormErrors;
  request: DataJobRequest | null;
} {
  const errors: FormErrors = {};
  const symbol = form.symbol.trim();
  const start = utcMilliseconds(form.start);
  const end = utcMilliseconds(form.end);

  if (!symbol) {
    errors.symbol = "심볼을 입력하세요.";
  } else if (symbol.length > 60 || !symbolPattern.test(symbol)) {
    errors.symbol = "BASE/QUOTE:SETTLE 형식의 CCXT 선물 심볼을 입력하세요.";
  }
  if (!form.start || Number.isNaN(start)) {
    errors.start = "UTC 시작 시각을 입력하세요.";
  }
  if (!form.end || Number.isNaN(end)) {
    errors.end = "UTC 종료 시각을 입력하세요.";
  }
  if (!errors.start && !errors.end && start >= end) {
    errors.end = "종료 시각은 시작 시각보다 뒤여야 합니다.";
  } else if (!errors.start && !errors.end && end - start > MAX_RANGE_MS) {
    errors.end = `기간은 최대 ${MAX_RANGE_DAYS}일까지 실행할 수 있습니다.`;
  }
  if (form.operation === "refresh_aggregates" && form.timeframes.length === 0) {
    errors.timeframes = "집계할 타임프레임을 하나 이상 선택하세요.";
  }

  if (Object.keys(errors).length > 0) return { errors, request: null };
  const request: DataJobRequest = {
    operation: form.operation,
    symbol,
    exchange: "binance",
    start: new Date(start).toISOString(),
    end: new Date(end).toISOString(),
  };
  if (form.operation === "refresh_aggregates") {
    request.timeframes = form.timeframes;
  }
  return { errors, request };
}

function operationLabel(operation: DataJobOperation): string {
  if (operation === "backfill") return "backfill · OHLCV 1분봉";
  if (operation === "funding_backfill") {
    return "funding_backfill · 펀딩비";
  }
  return "refresh_aggregates · 상위 타임프레임 집계";
}

function statusVariant(status: DataJobStatus["status"]): BadgeProps["variant"] {
  if (status === "SUCCEEDED") return "success";
  if (status === "FAILED") return "destructive";
  return "warning";
}

function StatusIcon({ status }: { status: DataJobStatus["status"] }) {
  if (status === "SUCCEEDED") {
    return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
  }
  if (status === "FAILED") {
    return <XCircle className="h-4 w-4 text-red-400" />;
  }
  if (status === "RUNNING") {
    return <LoaderCircle className="h-4 w-4 animate-spin text-amber-300" />;
  }
  return <Clock3 className="h-4 w-4 text-amber-300" />;
}

function Coverage({ item }: { item: InventoryItem }) {
  const label = coverageFormatter.format(item.coverage_ratio);
  return (
    <div className="flex min-w-32 items-center gap-2">
      <progress
        aria-label={`${item.symbol} 커버리지`}
        aria-valuetext={label}
        className="h-1.5 w-20 accent-teal-400"
        max={1}
        value={item.coverage_ratio}
      />
      <Badge variant="outline" className="min-w-16 justify-center tabular">
        {label}
      </Badge>
    </div>
  );
}

function InventoryLoading() {
  return (
    <div aria-label="데이터 인벤토리 로딩" className="space-y-2 p-4">
      {Array.from({ length: 5 }, (_, index) => (
        <Skeleton key={index} className="h-12 w-full" />
      ))}
    </div>
  );
}

function DataJobRow({ initialJob }: { initialJob: DataJobStatus }) {
  const query = useDataJob(initialJob.job_id, initialJob);
  const job = query.data ?? initialJob;

  return (
    <div
      className="rounded-lg border bg-background/45 p-4"
      data-testid={`data-job-${job.job_id}`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5">
          <StatusIcon status={job.status} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{job.symbol}</p>
            <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
            <Badge variant="outline">{job.operation}</Badge>
          </div>
          <p className="mt-1 font-mono text-[10px] text-muted-foreground">
            job {job.job_id} · {job.exchange}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            {formatTimestamp(job.start)} → {formatTimestamp(job.end)}
          </p>
          {job.timeframes && job.timeframes.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              timeframes {job.timeframes.join(", ")}
            </p>
          )}
          {job.status === "QUEUED" && (
            <p className="mt-2 text-xs text-muted-foreground">
              앞선 데이터 작업이 끝나면 실행을 시작합니다.
            </p>
          )}
          {job.status === "RUNNING" && (
            <div className="mt-3">
              <div
                role="progressbar"
                aria-label={`${job.symbol} 데이터 작업 실행 중`}
                aria-valuetext="서버 수치 진행률 미제공"
                className="h-1.5 overflow-hidden rounded-full bg-muted"
              >
                <div className="h-full w-full animate-pulse bg-gradient-to-r from-transparent via-amber-400/80 to-transparent" />
              </div>
              <p className="mt-1.5 text-[10px] text-muted-foreground">
                서버가 수치 진행률을 제공하지 않아 완료율은 표시하지 않습니다.
              </p>
            </div>
          )}
          {job.error && (
            <div className="mt-3 rounded-md border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-200">
              <p className="font-semibold">{job.error.code}</p>
              <p className="mt-1 break-words">{job.error.message}</p>
            </div>
          )}
          {query.isError && job.status !== "FAILED" && (
            <p className="mt-2 text-xs text-red-300">
              최신 상태를 불러오지 못했습니다. 자동으로 다시 시도합니다.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function ConfirmationDialog({
  request,
  busy,
  onCancel,
  onConfirm,
}: {
  request: DataJobRequest | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog
      open={request !== null}
      onOpenChange={(open) => {
        if (!open && !busy) onCancel();
      }}
    >
      <DialogContent className="border-amber-500/30">
        <div className="flex items-start gap-3 pr-6">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
          <div>
            <DialogTitle>실제 시장 데이터 쓰기를 실행하시겠습니까?</DialogTitle>
            <DialogDescription className="mt-1 text-amber-100/80">
              이 확인 뒤 collector가 Binance에 접근하고 crypto_data를 변경합니다.
              읽기 전용 조회나 DRY-RUN이 아닙니다.
            </DialogDescription>
          </div>
        </div>
        {request && (
          <dl className="grid gap-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 text-sm sm:grid-cols-[7rem_1fr]">
            <dt className="text-muted-foreground">심볼</dt>
            <dd className="font-medium">{request.symbol}</dd>
            <dt className="text-muted-foreground">거래소</dt>
            <dd>{request.exchange}</dd>
            <dt className="text-muted-foreground">작업</dt>
            <dd>{operationLabel(request.operation)}</dd>
            <dt className="text-muted-foreground">기간 (UTC)</dt>
            <dd className="tabular">
              {formatTimestamp(request.start)} → {formatTimestamp(request.end)}
            </dd>
            {request.timeframes && (
              <>
                <dt className="text-muted-foreground">timeframes</dt>
                <dd>{request.timeframes.join(", ")}</dd>
              </>
            )}
          </dl>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel} disabled={busy}>
            취소
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={busy}>
            {busy ? (
              <LoaderCircle className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-1.5 h-4 w-4" />
            )}
            실행
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function DataPage() {
  const inventory = useInventory(DATA_SOURCE);
  const dataJobs = useDataJobs();
  const items = inventory.data?.items ?? [];
  const inventorySymbols = useMemo(
    () => Array.from(new Set(items.map((item) => item.symbol))),
    [items],
  );
  const [form, setForm] = useState<DataJobForm>(initialForm);
  const [errors, setErrors] = useState<FormErrors>({});
  const [confirmation, setConfirmation] = useState<DataJobRequest | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function updateForm<K extends keyof DataJobForm>(
    key: K,
    value: DataJobForm[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  function toggleTimeframe(timeframe: AggregateTimeframe) {
    setForm((current) => ({
      ...current,
      timeframes: current.timeframes.includes(timeframe)
        ? current.timeframes.filter((value) => value !== timeframe)
        : [...current.timeframes, timeframe],
    }));
    setErrors((current) => ({ ...current, timeframes: undefined }));
  }

  function prepareConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    const result = validateForm(form);
    setErrors(result.errors);
    if (result.request) setConfirmation(result.request);
  }

  async function confirmExecution() {
    if (!confirmation) return;
    try {
      await dataJobs.trigger(confirmation);
      setConfirmation(null);
    } catch (error) {
      const message =
        error instanceof ApiRequestError && error.code
          ? `${error.code}: ${error.message}`
          : error instanceof Error
            ? error.message
            : "데이터 작업을 실행하지 못했습니다.";
      setSubmitError(message);
      setConfirmation(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-teal-300" />
            <h1 className="text-xl font-semibold tracking-tight">시장 데이터 인벤토리</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            백테스트가 조회하는 심볼별 1분봉 기간과 연속 커버리지를 확인합니다.
          </p>
        </div>
        <Badge variant="success" className="gap-1.5">
          <ShieldCheck className="h-3 w-3" />
          인벤토리 조회만 읽기 전용
        </Badge>
      </div>

      <div
        role="note"
        className="flex items-start gap-2 rounded-lg border border-teal-500/20 bg-teal-500/10 p-3 text-sm text-teal-100"
      >
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          crypto_data는 1분봉만 저장하며 상위 타임프레임은 연속집계입니다.
          아래 수집·실행 섹션은 이 읽기 전용 인벤토리와 별도의 쓰기 작업입니다.
        </p>
      </div>

      <Card className="overflow-hidden shadow-glow">
        <CardHeader>
          <CardTitle>OHLCV 커버리지</CardTitle>
          <CardDescription className="font-mono">{DATA_SOURCE}</CardDescription>
        </CardHeader>

        {inventory.isLoading ? (
          <InventoryLoading />
        ) : inventory.isError ? (
          <CardContent className="grid min-h-72 place-items-center p-8 text-center">
            <div>
              <AlertTriangle className="mx-auto h-8 w-8 text-red-400" />
              <p className="mt-3 font-medium">데이터 인벤토리를 불러오지 못했습니다.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {inventory.error.message}
              </p>
              <Button className="mt-4" onClick={() => void inventory.refetch()}>
                다시 시도
              </Button>
            </div>
          </CardContent>
        ) : items.length === 0 ? (
          <CardContent className="grid min-h-72 place-items-center p-8 text-center">
            <div>
              <Database className="mx-auto h-8 w-8 text-muted-foreground" />
              <p className="mt-3 font-medium">저장된 1분봉 데이터가 없습니다.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                이 데이터 소스에서 조회 가능한 심볼이 없습니다.
              </p>
            </div>
          </CardContent>
        ) : (
          <Table>
            <TableHeader className="bg-card">
              <TableRow>
                <TableHead>심볼</TableHead>
                <TableHead>거래소</TableHead>
                <TableHead>타임프레임</TableHead>
                <TableHead>기간</TableHead>
                <TableHead className="text-right">건수</TableHead>
                <TableHead className="text-right">예상 1m</TableHead>
                <TableHead className="text-right">누락 갭</TableHead>
                <TableHead>커버리지</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={`${item.symbol}:${item.exchange}`}>
                  <TableCell className="font-medium">{item.symbol}</TableCell>
                  <TableCell>{item.exchange}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{item.timeframe}</Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs tabular text-muted-foreground">
                    {period(item)}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {item.row_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {item.expected_1m_rows.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    <span
                      className={
                        item.missing_1m_rows > 0
                          ? "text-amber-300"
                          : "text-emerald-300"
                      }
                    >
                      {item.missing_1m_rows.toLocaleString()}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Coverage item={item} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <section aria-labelledby="data-job-title" className="space-y-4 pt-2">
        <div>
          <h2 id="data-job-title" className="text-lg font-semibold">
            데이터 수집·실행
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Binance 시장 데이터를 수집하거나 crypto_data 집계를 새로 만듭니다.
          </p>
        </div>

        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100"
        >
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
          <div>
            <p className="font-semibold">실제 쓰기 작업 · DRY-RUN 아님</p>
            <p className="mt-1">
              이 작업은 실제 시장 데이터를 crypto_data에 씁니다. 읽기 전용 조회가
              아닙니다. 제출 뒤 확인 Dialog에서 내용을 다시 확인해야 실행됩니다.
            </p>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(22rem,0.85fr)]">
          <Card>
            <CardHeader>
              <CardTitle>수집·backfill 설정</CardTitle>
              <CardDescription>
                기간은 UTC, 종료 시각은 포함하지 않는 [start, end) 범위입니다.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form noValidate onSubmit={prepareConfirmation} className="space-y-5">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1.5 text-sm">
                    <label htmlFor="data-job-symbol" className="block font-medium">
                      심볼 (CCXT 형식)
                    </label>
                    <Input
                      id="data-job-symbol"
                      aria-describedby={errors.symbol ? "symbol-error" : "symbol-help"}
                      aria-invalid={Boolean(errors.symbol)}
                      list="inventory-symbols"
                      maxLength={60}
                      placeholder="BTC/USDT:USDT"
                      value={form.symbol}
                      onChange={(event) => updateForm("symbol", event.target.value)}
                    />
                    <datalist id="inventory-symbols">
                      {inventorySymbols.map((symbol) => (
                        <option key={symbol} value={symbol} />
                      ))}
                    </datalist>
                    {errors.symbol ? (
                      <span id="symbol-error" className="block text-xs text-red-300">
                        {errors.symbol}
                      </span>
                    ) : (
                      <span id="symbol-help" className="block text-xs text-muted-foreground">
                        인벤토리에서 선택하거나 직접 입력할 수 있습니다.
                      </span>
                    )}
                  </div>

                  <div className="space-y-1.5 text-sm">
                    <label htmlFor="data-job-exchange" className="block font-medium">
                      거래소
                    </label>
                    <Input id="data-job-exchange" value="binance" disabled />
                    <span className="block text-xs text-muted-foreground">
                      현재 지원되는 유일한 거래소입니다.
                    </span>
                  </div>
                </div>

                <div className="space-y-1.5 text-sm">
                  <label htmlFor="data-job-operation" className="block font-medium">
                    작업
                  </label>
                  <select
                    id="data-job-operation"
                    className="flex h-9 w-full rounded-md border border-input bg-background/70 px-3 py-1 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    value={form.operation}
                    onChange={(event) =>
                      updateForm(
                        "operation",
                        event.target.value as DataJobOperation,
                      )
                    }
                  >
                    <option value="backfill">backfill · OHLCV 1분봉</option>
                    <option value="funding_backfill">
                      funding_backfill · 펀딩비
                    </option>
                    <option value="refresh_aggregates">
                      refresh_aggregates · 상위 타임프레임 집계
                    </option>
                  </select>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1.5 text-sm">
                    <label htmlFor="data-job-start" className="block font-medium">
                      시작 (UTC)
                    </label>
                    <Input
                      id="data-job-start"
                      type="datetime-local"
                      aria-invalid={Boolean(errors.start)}
                      value={form.start}
                      onChange={(event) => updateForm("start", event.target.value)}
                    />
                    {errors.start && (
                      <span className="block text-xs text-red-300">{errors.start}</span>
                    )}
                  </div>
                  <div className="space-y-1.5 text-sm">
                    <label htmlFor="data-job-end" className="block font-medium">
                      종료 (UTC)
                    </label>
                    <Input
                      id="data-job-end"
                      type="datetime-local"
                      aria-invalid={Boolean(errors.end)}
                      value={form.end}
                      onChange={(event) => updateForm("end", event.target.value)}
                    />
                    {errors.end && (
                      <span className="block text-xs text-red-300">{errors.end}</span>
                    )}
                  </div>
                </div>

                {form.operation === "refresh_aggregates" && (
                  <fieldset className="space-y-2">
                    <legend className="text-sm font-medium">timeframes</legend>
                    <div className="flex flex-wrap gap-2">
                      {timeframeOptions.map((timeframe) => (
                        <label
                          key={timeframe}
                          className="flex cursor-pointer items-center gap-2 rounded-md border bg-background/50 px-3 py-2 text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={form.timeframes.includes(timeframe)}
                            onChange={() => toggleTimeframe(timeframe)}
                          />
                          {timeframe}
                        </label>
                      ))}
                    </div>
                    {errors.timeframes && (
                      <p className="text-xs text-red-300">{errors.timeframes}</p>
                    )}
                  </fieldset>
                )}

                {submitError && (
                  <div
                    role="alert"
                    className="rounded-md border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-200"
                  >
                    {submitError}
                  </div>
                )}

                <div className="flex justify-end">
                  <Button type="submit" variant="destructive">
                    <AlertTriangle className="mr-1.5 h-4 w-4" />
                    실행 내용 확인
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle>데이터 작업 실행 큐</CardTitle>
                  <CardDescription>SSE 상태 스트림 · 서버 작업 목록</CardDescription>
                </div>
                <Badge variant="secondary">
                  {dataJobs.data?.length ?? 0} jobs
                </Badge>
              </div>
            </CardHeader>
            <CardContent aria-live="polite">
              <div className="max-h-[42rem] space-y-3 overflow-y-auto pr-1 scrollbar-thin">
                {dataJobs.isLoading ? (
                  <div aria-label="데이터 작업 목록 로딩" className="space-y-2">
                    <Skeleton className="h-28 w-full" />
                    <Skeleton className="h-28 w-full" />
                  </div>
                ) : dataJobs.isError ? (
                  <div className="rounded-lg border border-dashed p-6 text-center">
                    <AlertTriangle className="mx-auto h-6 w-6 text-red-400" />
                    <p className="mt-3 text-sm font-medium">
                      데이터 작업 목록을 불러오지 못했습니다.
                    </p>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-3"
                      onClick={() => void dataJobs.refetch()}
                    >
                      다시 시도
                    </Button>
                  </div>
                ) : (dataJobs.data?.length ?? 0) === 0 ? (
                  <div className="rounded-lg border border-dashed p-8 text-center">
                    <Clock3 className="mx-auto h-6 w-6 text-muted-foreground/60" />
                    <p className="mt-3 text-sm font-medium">
                      추적 중인 데이터 작업이 없습니다
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      실행을 확인하면 QUEUED부터 종단 상태까지 표시합니다.
                    </p>
                  </div>
                ) : (
                  dataJobs.data?.map((job) => (
                    <DataJobRow key={job.job_id} initialJob={job} />
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <ConfirmationDialog
        request={confirmation}
        busy={dataJobs.triggerState.isPending}
        onCancel={() => setConfirmation(null)}
        onConfirm={() => void confirmExecution()}
      />
    </div>
  );
}

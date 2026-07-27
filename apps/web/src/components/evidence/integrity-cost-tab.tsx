import { AlertTriangle, CheckCircle2, CircleX, ShieldCheck } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { RunSummary } from "../../api/client";
import { useIntegrityChecks } from "../../hooks/use-evidence";
import { formatDecimalString, formatMetric, formatTimestamp } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import {
  EvidenceError,
  EvidenceLoading,
  EvidenceTruncationNotice,
} from "./evidence-state";

export function IntegrityCostTab({
  runId,
  summary,
}: {
  runId: string;
  summary: RunSummary | null;
}) {
  const checks = useIntegrityChecks(runId);
  if (checks.isLoading) return <EvidenceLoading />;
  if (checks.error) return <EvidenceError error={checks.error} />;

  const costData = summary
    ? [
        { name: "Gross", value: summary.gross_pnl_total, color: "#2dd4bf" },
        { name: "Fee", value: summary.total_fee, color: "#fb7185" },
        { name: "Slip", value: summary.total_slippage, color: "#f97316" },
        { name: "Funding", value: summary.total_funding, color: "#f59e0b" },
        {
          name: "Penalty",
          value: summary.total_liquidation_penalty,
          color: "#ef4444",
        },
        { name: "Net", value: summary.net_pnl_total, color: "#38bdf8" },
      ]
    : [];
  const diagnosticOnly =
    summary !== null &&
    (!summary.integrity_passed || summary.integrity_status === "diagnostic_only");

  return (
    <div className="space-y-4">
      <EvidenceTruncationNotice sources={[checks.evidence]} />
      {diagnosticOnly && (
        <div className="flex gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">diagnostic_only · 판정 근거로 승격 불가</p>
            <p className="mt-1 text-xs text-amber-200/80">
              실패한 무결성 검사와 저장된 상세를 먼저 확인하세요.
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-teal-400" />
              무결성 검사
            </CardTitle>
            <CardDescription>
              INTEGRITY_CHECK {checks.data?.length ?? 0}행 · 실패 상세 자동 펼침
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {checks.data?.map((check) => (
              <details
                key={check.check_id}
                open={!check.passed}
                className="group rounded-lg border bg-background/35 p-3"
              >
                <summary className="flex cursor-pointer list-none items-center gap-2">
                  {check.passed ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <CircleX className="h-4 w-4 text-red-400" />
                  )}
                  <span className="flex-1 text-sm font-medium">{check.check_name}</span>
                  <Badge variant={check.passed ? "success" : "destructive"}>
                    {check.passed ? "passed" : "failed"}
                  </Badge>
                </summary>
                <div className="mt-3 border-t pt-3">
                  <p className="text-[10px] text-muted-foreground">
                    {formatTimestamp(check.checked_at)}
                    {check.sample_ref ? ` · ${check.sample_ref}` : ""}
                  </p>
                  {check.detail_json !== null && (
                    <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-[10px]">
                      {JSON.stringify(check.detail_json, null, 2)}
                    </pre>
                  )}
                </div>
              </details>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>데이터 커버리지</CardTitle>
            <CardDescription>backtest_summary 저장값</CardDescription>
          </CardHeader>
          <CardContent>
            {summary ? (
              <>
                <div className="flex items-end justify-between">
                  <span className="text-3xl font-semibold tabular">
                    {formatMetric(summary.data_coverage_ratio, {
                      style: "percent",
                      maximumFractionDigits: 2,
                    })}
                  </span>
                  <Badge
                    variant={summary.data_coverage_passed ? "success" : "destructive"}
                  >
                    {summary.data_coverage_passed ? "passed" : "failed"}
                  </Badge>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-teal-400"
                    style={{
                      width: `${Math.max(
                        0,
                        Math.min(100, summary.data_coverage_ratio * 100),
                      )}%`,
                    }}
                  />
                </div>
                <dl className="mt-5 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <dt className="text-muted-foreground">관측 / 기대</dt>
                    <dd className="mt-1 tabular font-medium">
                      {summary.observed_candle_count.toLocaleString()} /{" "}
                      {summary.expected_candle_count.toLocaleString()}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">최대 연속 갭</dt>
                    <dd className="mt-1 tabular font-medium">
                      {summary.max_consecutive_gap_bars} bars
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Funding 미관측</dt>
                    <dd className="mt-1 tabular font-medium">
                      {summary.unobservable_funding_boundary_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Gap exit</dt>
                    <dd className="mt-1 tabular font-medium">
                      {summary.data_gap_exit_count}
                    </dd>
                  </div>
                </dl>
              </>
            ) : (
              <p className="py-20 text-center text-sm text-muted-foreground">
                저장된 요약이 없어 커버리지를 표시할 수 없습니다.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>비용 워터폴</CardTitle>
          <CardDescription>
            저장된 Decimal 문자열을 Recharts에 전달하며 브라우저에서 합계를 재계산하지 않습니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {summary ? (
            <>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={costData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip
                      formatter={(_value, _name, item) => [
                        formatDecimalString(
                          (item.payload as (typeof costData)[number]).value,
                        ),
                        "저장값",
                      ]}
                    />
                    <Bar dataKey="value" isAnimationActive={false}>
                      {costData.map((item) => (
                        <Cell key={item.name} fill={item.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
                {costData.map((item) => (
                  <div key={item.name} className="rounded-md border p-2">
                    <p className="text-[10px] uppercase text-muted-foreground">
                      {item.name}
                    </p>
                    <p className="tabular mt-1 text-xs font-medium">
                      {formatDecimalString(item.value)}
                    </p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="py-20 text-center text-sm text-muted-foreground">
              저장된 비용 요약이 없습니다.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

import { BookOpenCheck, FileSearch, Target } from "lucide-react";
import {
  CartesianGrid,
  ErrorBar,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ConditionalExpectancy, RunSummary } from "../../api/client";
import { useResearchEvidence } from "../../hooks/use-evidence";
import { formatMetric, formatTimestamp } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import {
  EvidenceError,
  EvidenceLoading,
  EvidenceTruncationNotice,
} from "./evidence-state";

function observedMetric(summary: RunSummary | null, metric: string): number | null {
  if (!summary) return null;
  const metrics: Record<string, number | null> = {
    pf: summary.pf,
    sortino: summary.sortino,
    calmar: summary.calmar_or_mar,
    calmar_or_mar: summary.calmar_or_mar,
    sqn: summary.sqn,
    mdd: summary.mdd,
    ror: summary.ror,
    sharpe: summary.sharpe,
    win_rate: summary.win_rate,
    payoff: summary.payoff,
    expectancy_r: summary.expectancy_r,
    ulcer: summary.ulcer,
    psr: summary.psr,
  };
  return metrics[metric] ?? null;
}

function signatureLabel(item: ConditionalExpectancy): string {
  if (
    typeof item.definition_json === "object" &&
    item.definition_json !== null &&
    !Array.isArray(item.definition_json)
  ) {
    return Object.entries(item.definition_json)
      .map(([key, value]) => `${key}=${String(value)}`)
      .join(" · ");
  }
  return item.signature_key;
}

export function ResearchNotesTab({
  runId,
  summary,
}: {
  runId: string;
  summary: RunSummary | null;
}) {
  const evidence = useResearchEvidence(runId);
  if (
    evidence.conditional.isLoading ||
    evidence.findings.isLoading ||
    evidence.prereg.isLoading
  ) {
    return <EvidenceLoading />;
  }
  const error =
    evidence.conditional.error ?? evidence.findings.error ?? evidence.prereg.error;
  if (error) return <EvidenceError error={error} />;

  const conditional = evidence.conditional.data ?? [];
  const findings = evidence.findings.data ?? [];
  const prereg = evidence.prereg.data?.prereg ?? null;
  const chartData = conditional.map((item, index) => ({
    name: signatureLabel(item),
    index,
    expectancy: item.expectancy_r,
    error:
      item.expectancy_r !== null && item.ci_low !== null && item.ci_high !== null
        ? [
            Math.max(0, item.expectancy_r - item.ci_low),
            Math.max(0, item.ci_high - item.expectancy_r),
          ]
        : [0, 0],
  }));

  return (
    <div className="space-y-4">
      <EvidenceTruncationNotice sources={[evidence.conditional.data, evidence.findings.data]} />
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4 text-teal-400" />
              조건부 기대값
            </CardTitle>
            <CardDescription>
              CONDITION_SIGNATURE × CONDITIONAL_EXPECTANCY · 0선과 저장 CI
            </CardDescription>
          </CardHeader>
          <CardContent>
            {conditional.length ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ left: 16, right: 24 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                    <XAxis
                      type="number"
                      dataKey="expectancy"
                      name="기대값 R"
                      domain={["auto", "auto"]}
                    />
                    <YAxis type="number" dataKey="index" hide />
                    <ReferenceLine x={0} stroke="#94a3b8" strokeDasharray="4 4" />
                    <Tooltip
                      cursor={{ strokeDasharray: "3 3" }}
                      formatter={(value) => formatMetric(Number(value))}
                      labelFormatter={(_label, payload) =>
                        payload[0]?.payload?.name ?? ""
                      }
                    />
                    <Scatter data={chartData} fill="#2dd4bf" isAnimationActive={false}>
                      <ErrorBar
                        dataKey="error"
                        direction="x"
                        stroke="#5eead4"
                        strokeWidth={2}
                        width={8}
                      />
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="grid min-h-72 place-items-center rounded-lg border border-dashed text-center">
                <div>
                  <FileSearch className="mx-auto h-8 w-8 text-muted-foreground" />
                  <p className="mt-3 font-medium">조건부 기대값은 미구현·유보 상태입니다.</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    이 지표는 아직 기록 경로가 미구현이라 유보되었습니다(3차).
                    CONDITION_SIGNATURE × CONDITIONAL_EXPECTANCY 기록 경로가 마련되면
                    표시됩니다.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpenCheck className="h-4 w-4 text-sky-400" />
              사전등록 대조
            </CardTitle>
            <CardDescription>잠긴 가설과 저장된 관측 지표를 나란히 표시</CardDescription>
          </CardHeader>
          <CardContent>
            {prereg ? (
              <dl className="space-y-4 text-sm">
                <div>
                  <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    가설
                  </dt>
                  <dd className="mt-1 leading-relaxed">{prereg.hypothesis}</dd>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-[10px] uppercase text-muted-foreground">
                      주지표
                    </dt>
                    <dd className="mt-1 font-medium">{prereg.primary_metric}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase text-muted-foreground">
                      관측
                    </dt>
                    <dd className="tabular mt-1 font-medium">
                      {formatMetric(observedMetric(summary, prereg.primary_metric))}
                    </dd>
                  </div>
                </div>
                <div>
                  <dt className="text-[10px] uppercase text-muted-foreground">성공 기준</dt>
                  <dd className="mt-1 rounded-md bg-muted/35 p-2 font-mono text-xs">
                    {JSON.stringify(prereg.success_criteria_json)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase text-muted-foreground">실패 기준</dt>
                  <dd className="mt-1 rounded-md bg-muted/35 p-2 font-mono text-xs">
                    {prereg.failure_criteria_json === null
                      ? "—"
                      : JSON.stringify(prereg.failure_criteria_json)}
                  </dd>
                </div>
                <div className="flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
                  <span>{prereg.declared_by}</span>
                  <Badge variant={prereg.locked_at ? "success" : "warning"}>
                    {prereg.locked_at
                      ? `잠금 ${formatTimestamp(prereg.locked_at)}`
                      : "잠기지 않음"}
                  </Badge>
                </div>
              </dl>
            ) : (
              <p className="py-24 text-center text-sm text-muted-foreground">
                이 실행에는 카탈로그 사전등록이 없습니다.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {conditional.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>조건 서명 표</CardTitle>
            <CardDescription>표본·승률·PF·기대값·신뢰구간은 저장 통계량</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>조건</TableHead>
                  <TableHead>n</TableHead>
                  <TableHead>승률</TableHead>
                  <TableHead>PF</TableHead>
                  <TableHead>기대값 R</TableHead>
                  <TableHead>CI</TableHead>
                  <TableHead>판정</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {conditional.map((item) => (
                  <TableRow key={item.ce_id}>
                    <TableCell>{signatureLabel(item)}</TableCell>
                    <TableCell>{item.sample_count}</TableCell>
                    <TableCell>
                      {formatMetric(item.win_rate, { style: "percent" })}
                    </TableCell>
                    <TableCell>{formatMetric(item.pf)}</TableCell>
                    <TableCell>{formatMetric(item.expectancy_r)}</TableCell>
                    <TableCell>
                      [{formatMetric(item.ci_low)}, {formatMetric(item.ci_high)}]
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.is_significant ? "success" : "secondary"}>
                        {item.is_significant ? "significant" : "0선 포함"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>연구 노트 · FINDING_CLAIM</CardTitle>
          <CardDescription>
            읽기 전용 · 사후 주석층이며 결정성 Evidence hash에서 제외
          </CardDescription>
        </CardHeader>
        <CardContent>
          {findings.length ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {findings.map((finding) => (
                <article key={finding.finding_id} className="rounded-lg border p-4">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="outline">{finding.confidence}</Badge>
                    <span className="text-[10px] text-muted-foreground">
                      {formatTimestamp(finding.created_at)}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed">{finding.claim}</p>
                  {finding.proposed_change && (
                    <p className="mt-2 text-xs text-teal-300">
                      제안: {finding.proposed_change}
                    </p>
                  )}
                  <details className="mt-3 text-xs text-muted-foreground">
                    <summary className="cursor-pointer">근거 참조</summary>
                    <pre className="mt-2 overflow-auto whitespace-pre-wrap">
                      {JSON.stringify(finding.evidence_ref_json, null, 2)}
                    </pre>
                  </details>
                </article>
              ))}
            </div>
          ) : (
            <p className="py-14 text-center text-sm text-muted-foreground">
              연구 노트(FINDING_CLAIM)는 아직 기록 경로가 미구현이라
              유보되었습니다(3차). 기록 경로가 마련되면 이 위치에서 근거와 함께
              표시됩니다.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

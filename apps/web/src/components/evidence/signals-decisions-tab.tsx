import { AlertTriangle, FilterX, GitBranch, ShieldX } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CandidateEvent, Decision, Signal } from "../../api/client";
import {
  useCandidateEvents,
  useDecisions,
  useMissedOpportunities,
  useSignals,
} from "../../hooks/use-evidence";
import { formatMetric, formatTimestamp } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import {
  EvidenceError,
  EvidenceLoading,
  EvidenceTruncationNotice,
} from "./evidence-state";

type DistributionDatum = { name: string; count: number };

function distribution(
  values: Array<string | null>,
  priorityTerms: string[],
): DistributionDatum[] {
  const counts = new Map<string, number>();
  values.forEach((value) => {
    if (value) counts.set(value, (counts.get(value) ?? 0) + 1);
  });
  return [...counts]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => {
      const leftPriority = priorityTerms.some((term) => left.name.includes(term)) ? 0 : 1;
      const rightPriority = priorityTerms.some((term) => right.name.includes(term)) ? 0 : 1;
      return leftPriority - rightPriority || right.count - left.count;
    });
}

function ReasonChart({
  title,
  data,
  color,
  onSelect,
}: {
  title: string;
  data: DistributionDatum[];
  color: string;
  onSelect: (reason: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>막대를 누르면 아래 Evidence 목록이 같은 사유로 필터됩니다.</CardDescription>
      </CardHeader>
      <CardContent className="h-60">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 16 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={130} />
              <Tooltip />
              <Bar
                dataKey="count"
                fill={color}
                isAnimationActive={false}
                onClick={(entry) => onSelect((entry.payload as DistributionDatum).name)}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="grid h-full place-items-center text-sm text-muted-foreground">
            저장된 사유가 없습니다.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function stale(signal: Signal | undefined): boolean {
  return (
    signal?.is_warmup === true ||
    (signal !== undefined &&
      new Date(signal.feature_ts).getTime() < new Date(signal.decision_ts).getTime())
  );
}

function DecisionTable({
  decisions,
  signals,
}: {
  decisions: Decision[];
  signals: Map<number, Signal>;
}) {
  return (
    <div className="max-h-[560px] overflow-auto scrollbar-thin">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>시각</TableHead>
            <TableHead>신호</TableHead>
            <TableHead>판단</TableHead>
            <TableHead>방향 / 신뢰도</TableHead>
            <TableHead>skip_reason</TableHead>
            <TableHead>계획 체결</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {decisions.map((decision) => {
            const signal = decision.signal_id ? signals.get(decision.signal_id) : undefined;
            const freshnessWarning = stale(signal);
            return (
              <TableRow key={decision.decision_id}>
                <TableCell className="whitespace-nowrap">
                  {formatTimestamp(decision.decision_ts)}
                </TableCell>
                <TableCell>
                  {signal ? (
                    <div>
                      <span className="font-mono text-xs">S{signal.signal_id}</span>
                      <p className="max-w-52 truncate text-[10px] text-muted-foreground">
                        {signal.reason}
                      </p>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">시스템 판단</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={decision.action === "skip" ? "warning" : "secondary"}>
                    {decision.action}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span>{signal?.derived_side ?? decision.intended_side ?? "—"}</span>
                    <span className="tabular text-muted-foreground">
                      {signal ? formatMetric(signal.confidence) : "—"}
                    </span>
                    {freshnessWarning && (
                      <span
                        title={
                          signal?.is_warmup
                            ? "warmup 지표 기반 신호"
                            : "feature_ts가 decision_ts보다 뒤처짐"
                        }
                      >
                        <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>{decision.skip_reason ?? "—"}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {decision.planned_execution_ts
                    ? formatTimestamp(decision.planned_execution_ts)
                    : "—"}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function CandidateTable({
  candidates,
  onSelectTrade,
}: {
  candidates: CandidateEvent[];
  onSelectTrade: (tradeId: number) => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>시각</TableHead>
          <TableHead>트리거</TableHead>
          <TableHead>방향</TableHead>
          <TableHead>blocked_by</TableHead>
          <TableHead>결과</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {candidates.map((candidate) => (
          <TableRow
            key={candidate.candidate_id}
            className={candidate.linked_trade_id ? "cursor-pointer" : undefined}
            onClick={() => {
              if (candidate.linked_trade_id) onSelectTrade(candidate.linked_trade_id);
            }}
          >
            <TableCell>{formatTimestamp(candidate.ts)}</TableCell>
            <TableCell>{candidate.trigger_rule}</TableCell>
            <TableCell>{candidate.would_be_side ?? "—"}</TableCell>
            <TableCell>{candidate.blocked_by ?? "—"}</TableCell>
            <TableCell>
              {candidate.realized ? (
                <Badge variant="success">거래 #{candidate.linked_trade_id}</Badge>
              ) : (
                <Badge variant="warning">차단</Badge>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function SignalsDecisionsTab({
  runId,
  onSelectTrade,
}: {
  runId: string;
  onSelectTrade: (tradeId: number) => void;
}) {
  const signalQuery = useSignals(runId);
  const decisionQuery = useDecisions(runId);
  const candidateQuery = useCandidateEvents(runId);
  const missedQuery = useMissedOpportunities(runId);
  const [action, setAction] = useState("");
  const [skipReason, setSkipReason] = useState("");
  const [blockedBy, setBlockedBy] = useState("");

  const signals = signalQuery.data ?? [];
  const decisions = decisionQuery.data ?? [];
  const candidates = candidateQuery.data ?? [];
  const signalById = useMemo(
    () => new Map(signals.map((signal) => [signal.signal_id, signal])),
    [signals],
  );
  const skipDistribution = useMemo(
    () => distribution(decisions.map((decision) => decision.skip_reason), ["reentry", "cooldown"]),
    [decisions],
  );
  const blockedDistribution = useMemo(
    () => distribution(candidates.map((candidate) => candidate.blocked_by), [
      "reentry",
      "cooldown",
    ]),
    [candidates],
  );
  const filteredDecisions = decisions.filter(
    (decision) =>
      (!action || decision.action === action) &&
      (!skipReason || decision.skip_reason === skipReason),
  );
  const filteredCandidates = candidates.filter(
    (candidate) => !blockedBy || candidate.blocked_by === blockedBy,
  );

  if (
    signalQuery.isLoading ||
    decisionQuery.isLoading ||
    candidateQuery.isLoading ||
    missedQuery.isLoading
  ) {
    return <EvidenceLoading />;
  }
  const error =
    signalQuery.error ?? decisionQuery.error ?? candidateQuery.error ?? missedQuery.error;
  if (error) return <EvidenceError error={error} />;

  return (
    <div className="space-y-4">
      <EvidenceTruncationNotice
        sources={[
          signalQuery.evidence,
          decisionQuery.evidence,
          candidateQuery.evidence,
          missedQuery.evidence,
        ]}
      />
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-teal-400" />
                신호 {signals.length.toLocaleString()} · 판단{" "}
                {decisions.length.toLocaleString()}
              </CardTitle>
              <CardDescription>
                SIGNAL ⨝ DECISION · 저장된 시점과 게이트 사유를 그대로 대조
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                value={action}
                onChange={(event) => setAction(event.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-xs"
              >
                <option value="">모든 action</option>
                {[...new Set(decisions.map((decision) => decision.action))].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
              <select
                value={skipReason}
                onChange={(event) => setSkipReason(event.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-xs"
              >
                <option value="">모든 skip_reason</option>
                {skipDistribution.map((value) => (
                  <option key={value.name}>{value.name}</option>
                ))}
              </select>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setAction("");
                  setSkipReason("");
                  setBlockedBy("");
                }}
              >
                <FilterX className="mr-1 h-3.5 w-3.5" />
                초기화
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <ReasonChart
          title="건너뜀 분포 · DECISION.skip_reason"
          data={skipDistribution}
          color="#c084fc"
          onSelect={setSkipReason}
        />
        <ReasonChart
          title="후보 차단 · CANDIDATE.blocked_by"
          data={blockedDistribution}
          color="#f59e0b"
          onSelect={setBlockedBy}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>판단 타임라인</CardTitle>
          <CardDescription>
            {filteredDecisions.length.toLocaleString()}건 · warmup 또는 feature_ts 지연은 ⚠
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DecisionTable decisions={filteredDecisions} signals={signalById} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldX className="h-4 w-4 text-amber-400" />
            후보와 놓친 기회
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="candidates">
            <TabsList>
              <TabsTrigger value="candidates">
                후보 {filteredCandidates.length}
              </TabsTrigger>
              <TabsTrigger value="missed">
                놓친 기회 {missedQuery.data?.length ?? 0}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="candidates" className="max-h-[520px] overflow-auto">
              {filteredCandidates.length ? (
                <CandidateTable
                  candidates={filteredCandidates}
                  onSelectTrade={onSelectTrade}
                />
              ) : (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  필터에 맞는 후보가 없습니다.
                </p>
              )}
            </TabsContent>
            <TabsContent value="missed">
              {missedQuery.data?.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>시각</TableHead>
                      <TableHead>원천 규칙</TableHead>
                      <TableHead>누락 사유</TableHead>
                      <TableHead>잠재 R</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {missedQuery.data.map((item) => (
                      <TableRow key={item.miss_id}>
                        <TableCell>{formatTimestamp(item.ts)}</TableCell>
                        <TableCell>{item.source_rule}</TableCell>
                        <TableCell>{item.missing_reason}</TableCell>
                        <TableCell>{formatMetric(item.potential_r)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  놓친 기회(MISSED_OPPORTUNITY)는 기록 경로가 미구현이라
                  유보되었습니다(3차). 후보 차단 사유는 후보 탭에서 확인하세요.
                </p>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

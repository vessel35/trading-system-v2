import { ChevronLeft, ChevronRight, Loader2, TriangleAlert } from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Trade } from "../../api/client";
import { useExecutions, useTradeDrawerEvidence } from "../../hooks/use-evidence";
import {
  formatDecimalString,
  formatMetric,
  formatTimestamp,
} from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "../ui/sheet";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-background/35 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function TradeDrawer({
  runId,
  trades,
  selectedTradeId,
  onSelect,
  onClose,
}: {
  runId: string;
  trades: Trade[];
  selectedTradeId: number | null;
  onSelect: (tradeId: number) => void;
  onClose: () => void;
}) {
  const index = trades.findIndex((trade) => trade.trade_id === selectedTradeId);
  const trade = index >= 0 ? trades[index] : null;
  const executions = useExecutions(runId, selectedTradeId ?? 0);
  const details = useTradeDrawerEvidence(runId, selectedTradeId);
  const loading =
    executions.isLoading ||
    details.funding.isLoading ||
    details.features.isLoading ||
    details.candidates.isLoading ||
    details.positions.isLoading;
  const features = details.features.data ?? [];
  const excursion = features
    .filter((feature) => feature.excursion_r !== null)
    .map((feature) => ({ phase: feature.phase.toUpperCase(), value: feature.excursion_r }));
  const lastPosition = details.positions.data?.at(-1);

  return (
    <Sheet
      open={selectedTradeId !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent>
        {trade ? (
          <>
            <div className="pr-10">
              <div className="flex flex-wrap items-center gap-2">
                <SheetTitle>
                  거래 #{trade.trade_id} · {trade.side} · {trade.symbol}
                </SheetTitle>
                {trade.liquidated && (
                  <Badge variant="destructive">
                    <TriangleAlert className="mr-1 h-3 w-3" />
                    LIQUIDATED
                  </Badge>
                )}
              </div>
              <SheetDescription className="mt-1">
                {formatTimestamp(trade.entry_time)} →{" "}
                {trade.exit_time ? formatTimestamp(trade.exit_time) : "진행 중"}
              </SheetDescription>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <Button
                size="sm"
                variant="outline"
                disabled={index <= 0}
                onClick={() => onSelect(trades[index - 1].trade_id)}
              >
                <ChevronLeft className="mr-1 h-3.5 w-3.5" />
                이전
              </Button>
              <span className="text-xs text-muted-foreground">
                {index + 1} / {trades.length}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={index < 0 || index >= trades.length - 1}
                onClick={() => onSelect(trades[index + 1].trade_id)}
              >
                다음
                <ChevronRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                ["진입가", formatDecimalString(trade.entry_price)],
                ["수량", formatDecimalString(trade.entry_quantity)],
                ["Net PnL", formatDecimalString(trade.net_pnl)],
                ["R", formatMetric(trade.r_multiple)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg border bg-background/45 p-3">
                  <p className="text-[10px] uppercase text-muted-foreground">{label}</p>
                  <p className="tabular mt-1 text-sm font-semibold">{value}</p>
                </div>
              ))}
            </div>

            {loading ? (
              <div className="grid min-h-56 place-items-center">
                <Loader2 className="h-6 w-6 animate-spin text-teal-400" />
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {(executions.data?.length ?? 0) > 0 && (
                  <Section title={`체결 · ${executions.data?.length ?? 0}`}>
                    <div className="space-y-2">
                      {executions.data?.map((execution) => (
                        <div
                          key={execution.execution_id}
                          className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-b pb-2 text-xs last:border-0"
                        >
                          <Badge variant={execution.side === "BUY" ? "success" : "warning"}>
                            {execution.side}
                          </Badge>
                          <span>{formatTimestamp(execution.execution_ts)}</span>
                          <span className="text-muted-foreground">{execution.order_type}</span>
                          <span className="tabular">
                            ref {formatDecimalString(execution.reference_price)} →{" "}
                            {formatDecimalString(execution.price)} · qty{" "}
                            {formatDecimalString(execution.quantity)}
                          </span>
                          <span className="text-muted-foreground">비용</span>
                          <span className="tabular">
                            fee {formatDecimalString(execution.fee)} · slip{" "}
                            {formatDecimalString(execution.slippage)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </Section>
                )}

                {(details.funding.data?.length ?? 0) > 0 && (
                  <Section title={`펀딩 · ${details.funding.data?.length ?? 0}`}>
                    <div className="max-h-48 space-y-2 overflow-y-auto scrollbar-thin">
                      {details.funding.data?.map((settlement) => (
                        <div
                          key={settlement.settlement_id}
                          className="flex justify-between gap-4 border-b pb-2 text-xs last:border-0"
                        >
                          <span>
                            {formatTimestamp(settlement.settled_at)} ·{" "}
                            {formatMetric(settlement.funding_rate, {
                              style: "percent",
                              maximumFractionDigits: 4,
                            })}{" "}
                            ({settlement.rate_source})
                          </span>
                          <span className="tabular font-medium">
                            {formatDecimalString(settlement.payment_amount)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </Section>
                )}

                {features.length > 0 && (
                  <Section title="거래 특징">
                    {excursion.length > 0 && (
                      <div className="mb-3 h-32">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={excursion} layout="vertical">
                            <XAxis type="number" />
                            <YAxis
                              type="category"
                              dataKey="phase"
                              width={44}
                              interval={0}
                            />
                            <Tooltip />
                            <Bar dataKey="value" fill="#2dd4bf" isAnimationActive={false} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    <div className="space-y-2">
                      {features.map((feature) => (
                        <details key={feature.tfs_id} className="rounded border p-2 text-xs">
                          <summary className="cursor-pointer font-medium">
                            {feature.phase} · {feature.regime_tag ?? "regime —"} · R{" "}
                            {formatMetric(feature.excursion_r)}
                          </summary>
                          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[10px] text-muted-foreground">
                            {JSON.stringify(feature.features_json, null, 2)}
                          </pre>
                        </details>
                      ))}
                    </div>
                  </Section>
                )}

                {(details.candidates.data?.length ?? 0) > 0 && (
                  <Section title="후보 연결">
                    {details.candidates.data?.map((candidate) => (
                      <details key={candidate.candidate_id} className="text-xs">
                        <summary className="cursor-pointer font-medium">
                          {candidate.trigger_rule} ·{" "}
                          {candidate.realized ? "realized" : candidate.blocked_by}
                        </summary>
                        <pre className="mt-2 whitespace-pre-wrap text-[10px] text-muted-foreground">
                          {JSON.stringify(candidate.passed_filters_json, null, 2)}
                        </pre>
                      </details>
                    ))}
                  </Section>
                )}

                {lastPosition && (
                  <Section title={`포지션 · ${details.positions.data?.length ?? 0} snapshots`}>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <span className="text-muted-foreground">마지막 mark</span>
                      <span className="tabular text-right">
                        {formatDecimalString(lastPosition.mark_price)}
                      </span>
                      <span className="text-muted-foreground">미실현 PnL</span>
                      <span className="tabular text-right">
                        {formatDecimalString(lastPosition.unrealized_pnl)}
                      </span>
                      <span className="text-muted-foreground">청산가</span>
                      <span className="tabular text-right">
                        {formatDecimalString(lastPosition.liquidation_price)}
                      </span>
                      <span className="text-muted-foreground">펀딩 누계</span>
                      <span className="tabular text-right">
                        {formatDecimalString(lastPosition.funding_fee_total)}
                      </span>
                    </div>
                  </Section>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="grid min-h-64 place-items-center text-sm text-muted-foreground">
            거래를 찾을 수 없습니다.
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

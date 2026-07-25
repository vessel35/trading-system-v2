import { useVirtualizer } from "@tanstack/react-virtual";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, FilterX, TriangleAlert } from "lucide-react";
import { useMemo, useRef, useState } from "react";
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

import type { OutcomeBucket, Trade } from "../../api/client";
import { useOutcomeBuckets, useTrades } from "../../hooks/use-evidence";
import { cn, formatDecimalString, formatMetric, formatTimestamp } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { EvidenceError, EvidenceLoading } from "./evidence-state";

const column = createColumnHelper<Trade>();

type RBin = { label: string; min: number; max: number; count: number };

const R_BINS: Omit<RBin, "count">[] = [
  { label: "≤ -2R", min: Number.NEGATIVE_INFINITY, max: -2 },
  { label: "-2~-1R", min: -2, max: -1 },
  { label: "-1~0R", min: -1, max: 0 },
  { label: "0~1R", min: 0, max: 1 },
  { label: "1~2R", min: 1, max: 2 },
  { label: "≥ 2R", min: 2, max: Number.POSITIVE_INFINITY },
];

function rHistogram(trades: Trade[]): RBin[] {
  return R_BINS.map((bin) => ({
    ...bin,
    count: trades.filter(
      (trade) =>
        trade.r_multiple !== null &&
        trade.r_multiple >= bin.min &&
        (bin.max === Number.POSITIVE_INFINITY
          ? trade.r_multiple <= bin.max
          : trade.r_multiple < bin.max),
    ).length,
  }));
}

function outcomeCounts(buckets: OutcomeBucket[]) {
  const counts = new Map<string, number>();
  for (const bucket of buckets) {
    counts.set(bucket.bucket_value, (counts.get(bucket.bucket_value) ?? 0) + 1);
  }
  return [...counts].map(([name, count]) => ({ name, count }));
}

function VirtualTradeTable({
  trades,
  onSelectTrade,
}: {
  trades: Trade[];
  onSelectTrade: (tradeId: number) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "trade_id", desc: false }]);
  const columns = useMemo(
    () => [
      column.accessor("trade_id", { header: "#", cell: (info) => `#${info.getValue()}` }),
      column.accessor("side", {
        header: "방향",
        cell: (info) => (
          <Badge variant={info.getValue() === "LONG" ? "success" : "warning"}>
            {info.getValue()}
          </Badge>
        ),
      }),
      column.accessor("entry_time", {
        header: "진입",
        cell: (info) => formatTimestamp(info.getValue()),
      }),
      column.accessor("exit_reason", {
        header: "청산 사유",
        cell: (info) => info.getValue() ?? "OPEN",
      }),
      column.accessor("net_pnl", {
        header: "Net PnL",
        cell: (info) => (
          <span className="tabular font-medium">{formatDecimalString(info.getValue())}</span>
        ),
      }),
      column.accessor("r_multiple", {
        header: "R",
        cell: (info) => (
          <span className="tabular">
            {info.getValue() === null ? "R 제외" : formatMetric(info.getValue())}
          </span>
        ),
      }),
      column.accessor("hold_duration_seconds", {
        header: "보유",
        cell: (info) =>
          info.getValue() === null ? "—" : `${Math.round(info.getValue()! / 3600)}h`,
      }),
      column.accessor("liquidated", {
        header: "",
        cell: (info) =>
          info.getValue() ? <TriangleAlert className="h-4 w-4 text-red-400" /> : null,
      }),
    ],
    [],
  );
  const table = useReactTable({
    data: trades,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  const rows = table.getRowModel().rows;
  const viewport = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => viewport.current,
    estimateSize: () => 48,
    overscan: 8,
  });
  const template = "52px 86px minmax(170px,1.3fr) minmax(125px,1fr) minmax(130px,1fr) 90px 74px 32px";

  return (
    <div className="overflow-x-auto scrollbar-thin">
      <div className="min-w-[920px]">
        {table.getHeaderGroups().map((group) => (
          <div
            key={group.id}
            className="grid h-10 items-center border-b bg-muted/30 px-2"
            style={{ gridTemplateColumns: template }}
          >
            {group.headers.map((header) => (
              <button
                type="button"
                key={header.id}
                className="flex items-center gap-1 px-2 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground"
                onClick={header.column.getToggleSortingHandler()}
              >
                {flexRender(header.column.columnDef.header, header.getContext())}
                {header.column.getCanSort() && <ArrowUpDown className="h-3 w-3" />}
              </button>
            ))}
          </div>
        ))}
        <div ref={viewport} className="h-[480px] overflow-y-auto scrollbar-thin">
          <div className="relative" style={{ height: virtual.getTotalSize() }}>
            {virtual.getVirtualItems().map((virtualRow) => {
              const row = rows[virtualRow.index];
              return (
                <button
                  type="button"
                  key={row.id}
                  className="absolute left-0 grid w-full items-center border-b px-2 text-left text-xs transition-colors hover:bg-muted/45"
                  style={{
                    height: virtualRow.size,
                    transform: `translateY(${virtualRow.start}px)`,
                    gridTemplateColumns: template,
                  }}
                  onClick={() => onSelectTrade(row.original.trade_id)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <span key={cell.id} className="truncate px-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </span>
                  ))}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export function TradesTab({
  runId,
  onSelectTrade,
}: {
  runId: string;
  onSelectTrade: (tradeId: number) => void;
}) {
  const tradesQuery = useTrades(runId);
  const bucketsQuery = useOutcomeBuckets(runId);
  const [exitReason, setExitReason] = useState("");
  const [side, setSide] = useState("");
  const [outcome, setOutcome] = useState("");
  const [rRange, setRRange] = useState<{ min: number; max: number } | null>(null);
  const buckets = bucketsQuery.data ?? [];
  const outcomeByTrade = useMemo(
    () => new Map(buckets.map((bucket) => [bucket.subject_id, bucket.bucket_value])),
    [buckets],
  );
  const trades = tradesQuery.data ?? [];
  const baseFiltered = useMemo(
    () =>
      trades.filter(
        (trade) =>
          (!exitReason || trade.exit_reason === exitReason) &&
          (!side || trade.side === side) &&
          (!outcome || outcomeByTrade.get(trade.trade_id) === outcome),
      ),
    [exitReason, outcome, outcomeByTrade, side, trades],
  );
  const filtered = useMemo(
    () =>
      rRange === null
        ? baseFiltered
        : baseFiltered.filter(
            (trade) =>
              trade.r_multiple !== null &&
              trade.r_multiple >= rRange.min &&
              (rRange.max === Number.POSITIVE_INFINITY
                ? trade.r_multiple <= rRange.max
                : trade.r_multiple < rRange.max),
          ),
    [baseFiltered, rRange],
  );
  const histogram = useMemo(() => rHistogram(baseFiltered), [baseFiltered]);
  const bucketCounts = useMemo(() => outcomeCounts(buckets), [buckets]);
  const exitReasons = useMemo(
    () =>
      [...new Set(trades.map((trade) => trade.exit_reason).filter(Boolean))].sort() as string[],
    [trades],
  );

  if (tradesQuery.isLoading || bucketsQuery.isLoading) return <EvidenceLoading />;
  const error = tradesQuery.error ?? bucketsQuery.error;
  if (error) return <EvidenceError error={error} />;
  if (trades.length === 0) {
    return (
      <Card>
        <CardContent className="grid min-h-64 place-items-center text-center">
          <div>
            <p className="font-medium">거래가 없습니다.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              신호·의사결정 탭에서 진입 차단 사유를 확인하세요.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>거래 {filtered.length.toLocaleString()}건</CardTitle>
              <CardDescription>
                저장된 TRADE · R 제외{" "}
                {trades.filter((trade) => trade.r_multiple === null).length.toLocaleString()}건
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                value={exitReason}
                onChange={(event) => setExitReason(event.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-xs"
                aria-label="청산 사유"
              >
                <option value="">모든 청산 사유</option>
                {exitReasons.map((reason) => (
                  <option key={reason}>{reason}</option>
                ))}
              </select>
              <select
                value={side}
                onChange={(event) => setSide(event.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-xs"
                aria-label="방향"
              >
                <option value="">LONG + SHORT</option>
                <option>LONG</option>
                <option>SHORT</option>
              </select>
              <select
                value={outcome}
                onChange={(event) => setOutcome(event.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-xs"
                aria-label="결과 분류"
              >
                <option value="">모든 결과 분류</option>
                {bucketCounts.map((bucket) => (
                  <option key={bucket.name}>{bucket.name}</option>
                ))}
              </select>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setExitReason("");
                  setSide("");
                  setOutcome("");
                  setRRange(null);
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
        <Card>
          <CardHeader>
            <CardTitle>R-multiple 분포</CardTitle>
            <CardDescription>막대를 누르면 표와 분포를 같은 R 구간으로 브러싱합니다.</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={histogram}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                <XAxis dataKey="label" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar
                  dataKey="count"
                  isAnimationActive={false}
                  onClick={(entry) => {
                    const bin = entry.payload as RBin;
                    setRRange({ min: bin.min, max: bin.max });
                  }}
                >
                  {histogram.map((bin) => (
                    <Cell
                      key={bin.label}
                      fill={bin.max <= 0 ? "#fb7185" : "#2dd4bf"}
                      opacity={
                        rRange === null ||
                        (rRange.min === bin.min && rRange.max === bin.max)
                          ? 0.9
                          : 0.28
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>결과 버킷</CardTitle>
            <CardDescription>Engine이 저장한 OUTCOME_BUCKET 분류입니다.</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bucketCounts} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={110} />
                <Tooltip />
                <Bar
                  dataKey="count"
                  fill="#38bdf8"
                  isAnimationActive={false}
                  onClick={(entry) => {
                    const bucket = entry.payload as { name: string };
                    setOutcome(bucket.name);
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>거래 목록</CardTitle>
          <CardDescription>정렬 가능 · 가상 스크롤 · 행을 눌러 상세 열기</CardDescription>
        </CardHeader>
        <CardContent className={cn(filtered.length === 0 && "py-12 text-center")}>
          {filtered.length ? (
            <VirtualTradeTable trades={filtered} onSelectTrade={onSelectTrade} />
          ) : (
            <p className="text-sm text-muted-foreground">필터에 맞는 거래가 없습니다.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

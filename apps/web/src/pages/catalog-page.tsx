import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  type RowSelectionState,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  GitCompareArrows,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation } from "wouter";

import type { RunListItem } from "../api/client";
import { CatalogFilterBar } from "../components/catalog-filter-bar";
import { Badge, type BadgeProps } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../components/ui/dialog";
import { Skeleton } from "../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { useCatalogFilters } from "../contexts/catalog-filters";
import { useComparisonBasket } from "../contexts/comparison-basket";
import { useRuns, useSetRunDeleted } from "../hooks/use-catalog";
import {
  catalogDecisionPresentation,
  cn,
  formatDecimalString,
  formatMetric,
  formatPeriod,
  formatTimestamp,
  shortHash,
} from "../lib/utils";

const PAGE_SIZE = 50;

function statusVariant(status: string): BadgeProps["variant"] {
  if (status === "COMPLETED" || status === "EVALUATED") return "success";
  if (status === "RUNNING") return "warning";
  if (status === "FAILED") return "destructive";
  return "secondary";
}

function verdictVariant(verdict: string | null): BadgeProps["variant"] {
  if (verdict === "pass") return "success";
  if (!verdict) return "secondary";
  return verdict.includes("fail") || verdict.includes("not_")
    ? "destructive"
    : "warning";
}

function DecisionCell({ run }: { run: RunListItem }) {
  const decision = catalogDecisionPresentation(
    run.summary_present,
    run.gate_verdict,
    run.decision_route,
  );

  return (
    <div className="flex min-w-24 flex-col items-start gap-1">
      <Badge variant={run.summary_present ? verdictVariant(run.gate_verdict) : "secondary"}>
        {decision.label}
      </Badge>
      {decision.showRoute && (
        <span className="text-[10px] text-muted-foreground">{run.decision_route}</span>
      )}
    </div>
  );
}

export function CatalogPage() {
  const [, navigate] = useLocation();
  const { filters } = useCatalogFilters();
  const basket = useComparisonBasket();
  const setRunDeleted = useSetRunDeleted();
  const [offset, setOffset] = useState(0);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [pendingDeletion, setPendingDeletion] = useState<string[] | null>(null);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "created_at", desc: true },
  ]);

  useEffect(() => {
    setOffset(0);
    setRowSelection({});
  }, [filters]);

  const primarySort = sorting[0];
  const sort = primarySort
    ? `${primarySort.desc ? "-" : ""}${primarySort.id}`
    : "-created_at";
  const runsQuery = useRuns({
    ...filters,
    limit: PAGE_SIZE,
    offset,
    sort,
  });

  const columns = useMemo<ColumnDef<RunListItem>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <input
            type="checkbox"
            checked={table.getIsAllPageRowsSelected()}
            ref={(element) => {
              if (element) element.indeterminate = table.getIsSomePageRowsSelected();
            }}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            onClick={(event) => event.stopPropagation()}
            className="h-3.5 w-3.5 accent-teal-500"
            aria-label="현재 페이지 전체 선택"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
            onClick={(event) => event.stopPropagation()}
            className="h-3.5 w-3.5 accent-teal-500"
            aria-label={`${row.original.run_name} 선택`}
          />
        ),
        enableSorting: false,
      },
      {
        id: "created_at",
        header: "실행",
        cell: ({ row }) => (
          <div className="min-w-56">
            <div className="flex items-center gap-2">
              {row.original.status === "RUNNING" && (
                <LoaderCircle className="h-3 w-3 animate-spin text-amber-400" />
              )}
              <span className="max-w-48 truncate font-medium text-foreground">
                {row.original.run_name}
              </span>
              {row.original.deleted_at && <Badge variant="outline">삭제됨</Badge>}
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
              <span className="font-mono">{shortHash(row.original.run_id, 18)}</span>
              <span>{formatTimestamp(row.original.created_at)}</span>
            </div>
          </div>
        ),
        enableSorting: true,
      },
      {
        accessorKey: "status",
        header: "상태",
        cell: ({ getValue }) => {
          const status = String(getValue());
          return <Badge variant={statusVariant(status)}>{status}</Badge>;
        },
        enableSorting: false,
      },
      {
        accessorKey: "strategy_name",
        header: "전략",
        cell: ({ row }) => (
          <div>
            <p className="max-w-36 truncate text-xs">{row.original.strategy_name}</p>
            <p className="max-w-36 truncate text-[10px] text-muted-foreground">
              {row.original.strategy_id}
            </p>
          </div>
        ),
        enableSorting: false,
      },
      {
        id: "market",
        header: "대상",
        cell: ({ row }) => (
          <div className="whitespace-nowrap">
            <p className="text-xs font-medium">{row.original.symbol}</p>
            <p className="text-[10px] text-muted-foreground">
              {row.original.exchange} · {row.original.timeframe} ·{" "}
              {row.original.market_type}
            </p>
          </div>
        ),
        enableSorting: false,
      },
      {
        id: "period",
        header: "기간",
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-[11px] text-muted-foreground">
            {formatPeriod(row.original.period_start, row.original.period_end)}
          </span>
        ),
        enableSorting: false,
      },
      {
        accessorKey: "trade_count",
        header: "거래",
        cell: ({ getValue }) => (
          <span className="tabular text-xs">{formatMetric(getValue<number | null>())}</span>
        ),
        enableSorting: false,
      },
      {
        accessorKey: "pf",
        header: "PF",
        cell: ({ getValue }) => (
          <span className="tabular">{formatMetric(getValue<number | null>())}</span>
        ),
      },
      {
        accessorKey: "sortino",
        header: "Sortino",
        cell: ({ getValue }) => (
          <span className="tabular">{formatMetric(getValue<number | null>())}</span>
        ),
      },
      {
        accessorKey: "mdd",
        header: "MDD",
        cell: ({ getValue }) => (
          <span className="tabular text-red-300">
            {formatMetric(getValue<number | null>(), {
              style: "percent",
              maximumFractionDigits: 1,
            })}
          </span>
        ),
        enableSorting: false,
      },
      {
        accessorKey: "net_pnl_total",
        header: "순손익",
        cell: ({ getValue }) => (
          <span className="tabular whitespace-nowrap text-xs">
            {formatDecimalString(getValue<string | null>())}
          </span>
        ),
      },
      {
        id: "decision",
        header: "판정",
        cell: ({ row }) => <DecisionCell run={row.original} />,
        enableSorting: false,
      },
      {
        id: "determinism",
        header: "config",
        cell: ({ row }) => (
          <span className="font-mono text-[10px] text-muted-foreground">
            {shortHash(row.original.config_hash)}
          </span>
        ),
        enableSorting: false,
      },
      {
        id: "deletion",
        header: "삭제",
        cell: ({ row }) => {
          const run = row.original;
          const deleted = run.deleted_at !== null && run.deleted_at !== undefined;
          return (
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "h-7 px-2",
                deleted ? "text-teal-300" : "text-muted-foreground hover:text-red-300",
              )}
              disabled={setRunDeleted.isPending}
              aria-label={
                deleted ? `${run.run_name} 복원` : `${run.run_name} 삭제`
              }
              onClick={(event) => {
                event.stopPropagation();
                if (deleted) {
                  setRunDeleted.mutate({ runId: run.run_id, deleted: false });
                  return;
                }
                setPendingDeletion([run.run_id]);
              }}
            >
              {deleted ? (
                <RotateCcw className="h-3.5 w-3.5" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
            </Button>
          );
        },
        enableSorting: false,
      },
    ],
    [setRunDeleted],
  );

  const table = useReactTable({
    data: runsQuery.data?.data ?? [],
    columns,
    state: { rowSelection, sorting },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.run_id,
    manualSorting: true,
  });

  const selected = table.getSelectedRowModel().rows.map((row) => row.original);
  const selectedAlive = selected.filter((run) => !run.deleted_at);
  const selectedDeleted = selected.filter((run) => run.deleted_at);

  /**
   * Apply the marker run by run so one failure does not stop the rest, and
   * re-read the list only after the last one instead of once per run.
   */
  async function applyDeletion(runIds: string[], deleted: boolean) {
    for (const [index, runId] of runIds.entries()) {
      await setRunDeleted
        .mutateAsync({ runId, deleted, refresh: index === runIds.length - 1 })
        .catch(() => undefined);
    }
    setRowSelection({});
  }

  async function restoreRuns(runIds: string[]) {
    await applyDeletion(runIds, false);
  }

  const page = runsQuery.data?.page;
  const currentPage = page ? Math.floor(page.offset / page.limit) + 1 : 1;
  const pageCount = page ? Math.max(1, Math.ceil(page.total / page.limit)) : 1;

  return (
    <div className="mx-auto max-w-[1800px] space-y-4 p-4 md:p-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-teal-400">
              Catalog / Runs
            </p>
            <Badge variant="outline">READ ONLY</Badge>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">카탈로그 · 실행</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            저장된 실행과 저장 요약을 필터링하고 비교 후보를 고릅니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <p className="text-xs text-muted-foreground">
            <span className="tabular font-semibold text-foreground">
              {page?.total.toLocaleString() ?? "—"}
            </span>{" "}
            개 실행
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void runsQuery.refetch()}
            disabled={runsQuery.isFetching}
          >
            <RefreshCw
              className={cn("mr-1.5 h-3.5 w-3.5", runsQuery.isFetching && "animate-spin")}
            />
            새로고침
          </Button>
        </div>
      </div>

      <CatalogFilterBar />

      <Card className="overflow-hidden shadow-glow">
        {runsQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 9 }, (_, index) => (
              <Skeleton key={index} className="h-11 w-full" />
            ))}
          </div>
        ) : runsQuery.isError ? (
          <div className="grid min-h-80 place-items-center p-8 text-center">
            <div>
              <p className="font-medium">카탈로그를 불러오지 못했습니다.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {runsQuery.error.message}
              </p>
              <Button className="mt-4" onClick={() => void runsQuery.refetch()}>
                다시 시도
              </Button>
            </div>
          </div>
        ) : table.getRowModel().rows.length === 0 ? (
          <div className="grid min-h-80 place-items-center p-8 text-center">
            <div>
              <p className="font-medium">조건에 맞는 실행이 없습니다.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                필터를 줄이거나 생성일 범위를 넓혀 보세요.
              </p>
            </div>
          </div>
        ) : (
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card">
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder ? null : header.column.getCanSort() ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 hover:text-foreground"
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          {header.column.getIsSorted() === "asc" ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : header.column.getIsSorted() === "desc" ? (
                            <ArrowDown className="h-3 w-3" />
                          ) : (
                            <ArrowUpDown className="h-3 w-3 opacity-50" />
                          )}
                        </button>
                      ) : (
                        flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )
                      )}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  className={cn(
                    "cursor-pointer",
                    row.original.status === "FAILED" && "opacity-70",
                    row.original.deleted_at && "opacity-60",
                  )}
                  onClick={() => navigate(`/runs/${encodeURIComponent(row.original.run_id)}`)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <div className="flex min-h-14 flex-col gap-3 border-t bg-card/95 px-4 py-3 sm:flex-row sm:items-center">
          <div className="flex min-h-8 items-center gap-2">
            <span className="text-xs text-muted-foreground">
              선택 <strong className="tabular text-foreground">{selected.length}</strong>개
            </span>
            {selected.length > 0 && (
              <>
                <Button
                  size="sm"
                  onClick={() => {
                    basket.add(selected);
                    setRowSelection({});
                  }}
                >
                  <GitCompareArrows className="mr-1.5 h-3.5 w-3.5" />
                  비교에 담기
                </Button>
                {selectedAlive.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={setRunDeleted.isPending}
                    onClick={() =>
                      setPendingDeletion(selectedAlive.map((run) => run.run_id))
                    }
                  >
                    <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                    선택 삭제
                  </Button>
                )}
                {selectedDeleted.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={setRunDeleted.isPending}
                    onClick={() => {
                      void restoreRuns(selectedDeleted.map((run) => run.run_id));
                    }}
                  >
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                    선택 복원
                  </Button>
                )}
              </>
            )}
          </div>
          <div className="ml-auto flex items-center gap-3">
            <span className="tabular text-xs text-muted-foreground">
              {currentPage} / {pageCount}
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0 || runsQuery.isFetching}
                onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
              >
                <ChevronLeft className="mr-1 h-3.5 w-3.5" />
                이전
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!page?.has_more || runsQuery.isFetching}
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
              >
                다음
                <ChevronRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <Dialog
        open={pendingDeletion !== null}
        onOpenChange={(next) => {
          if (!next) setPendingDeletion(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogTitle>
            {`실행 ${pendingDeletion?.length ?? 0}개를 삭제할까요?`}
          </DialogTitle>
          <DialogDescription className="leading-relaxed">
            목록에서만 감춥니다. 저장된 실행 기록과 요약, 증거 파일은 그대로 남으며,
            필터를 "삭제만 보기"로 바꾸면 다시 찾아 복원할 수 있습니다.
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setPendingDeletion(null)}>
              취소
            </Button>
            <Button
              disabled={setRunDeleted.isPending}
              onClick={() => {
                const runIds = pendingDeletion ?? [];
                setPendingDeletion(null);
                void applyDeletion(runIds, true);
              }}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
              삭제
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

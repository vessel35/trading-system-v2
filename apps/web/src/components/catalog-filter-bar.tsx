import { RotateCcw, SlidersHorizontal } from "lucide-react";

import { useCatalogFilters } from "../contexts/catalog-filters";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

function dateValue(value: string | null | undefined): string {
  return value?.slice(0, 10) ?? "";
}

export function CatalogFilterBar() {
  const { filters, updateFilters, resetFilters, activeCount } = useCatalogFilters();

  return (
    <div className="rounded-xl border bg-card/65 p-3 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <SlidersHorizontal className="h-3.5 w-3.5 text-teal-400" />
        <span className="text-xs font-medium">전역 필터</span>
        {activeCount > 0 && <Badge variant="secondary">{activeCount} 활성</Badge>}
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          onClick={resetFilters}
          disabled={activeCount === 0}
        >
          <RotateCcw className="mr-1.5 h-3 w-3" />
          초기화
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-7">
        <Input
          value={filters.strategy_id ?? ""}
          onChange={(event) =>
            updateFilters({ strategy_id: event.target.value || undefined })
          }
          placeholder="전략 ID"
          aria-label="전략 ID 필터"
        />
        <Input
          value={filters.symbol ?? ""}
          onChange={(event) =>
            updateFilters({ symbol: event.target.value.toUpperCase() || undefined })
          }
          placeholder="심볼"
          aria-label="심볼 필터"
        />
        <Input
          value={filters.timeframe ?? ""}
          onChange={(event) =>
            updateFilters({ timeframe: event.target.value || undefined })
          }
          placeholder="타임프레임"
          aria-label="타임프레임 필터"
        />
        <select
          value={filters.status ?? ""}
          onChange={(event) => updateFilters({ status: event.target.value || undefined })}
          className="h-9 rounded-md border border-input bg-background/70 px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          aria-label="실행 상태 필터"
        >
          <option value="">모든 상태</option>
          <option value="RUNNING">RUNNING</option>
          <option value="COMPLETED">COMPLETED</option>
          <option value="EVALUATED">EVALUATED</option>
          <option value="FAILED">FAILED</option>
          <option value="ORPHANED">ORPHANED</option>
        </select>
        <select
          value={filters.decision_route ?? ""}
          onChange={(event) =>
            updateFilters({ decision_route: event.target.value || undefined })
          }
          className="h-9 rounded-md border border-input bg-background/70 px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          aria-label="판정 경로 필터"
        >
          <option value="">모든 route</option>
          <option value="promote">promote</option>
          <option value="partial_keep">partial_keep</option>
          <option value="abandon">abandon</option>
          <option value="retest">retest</option>
        </select>
        <select
          value={
            filters.gate_passed === undefined || filters.gate_passed === null
              ? ""
              : String(filters.gate_passed)
          }
          onChange={(event) =>
            updateFilters({
              gate_passed:
                event.target.value === "" ? undefined : event.target.value === "true",
            })
          }
          className="h-9 rounded-md border border-input bg-background/70 px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          aria-label="게이트 통과 필터"
        >
          <option value="">모든 gate</option>
          <option value="true">통과</option>
          <option value="false">미통과</option>
        </select>
        <div className="grid grid-cols-2 gap-1">
          <Input
            type="date"
            value={dateValue(filters.period_start_from)}
            onChange={(event) =>
              updateFilters({
                period_start_from: event.target.value
                  ? `${event.target.value}T00:00:00Z`
                  : undefined,
              })
            }
            aria-label="백테스트 기간 시작"
            className="px-2 text-xs"
          />
          <Input
            type="date"
            value={dateValue(filters.period_end_to)}
            onChange={(event) =>
              updateFilters({
                period_end_to: event.target.value
                  ? `${event.target.value}T23:59:59Z`
                  : undefined,
              })
            }
            aria-label="백테스트 기간 종료"
            className="px-2 text-xs"
          />
        </div>
      </div>
    </div>
  );
}

import {
  BarChart3,
  FlaskConical,
  LayoutList,
  Search,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useLocation } from "wouter";

import { apiClient, requestErrorMessage } from "../api/client";
import { useCatalogFilters } from "../contexts/catalog-filters";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./ui/dialog";
import { Input } from "./ui/input";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const commands = [
  {
    label: "카탈로그 실행 목록",
    description: "저장된 run과 요약 지표 탐색",
    path: "/runs",
    icon: LayoutList,
  },
  {
    label: "실행 비교 분석",
    description: "선택한 실행의 저장 지표와 설정 비교",
    path: "/compare",
    icon: BarChart3,
  },
  {
    label: "실행 관리",
    description: "dry-run 트리거·스윕과 실행 상태 확인",
    path: "/manage",
    icon: FlaskConical,
  },
] as const;

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const [, navigate] = useLocation();
  const { updateFilters } = useCatalogFilters();
  const [search, setSearch] = useState("");
  const runs = useQuery({
    queryKey: ["command-palette", "runs"],
    enabled: open,
    staleTime: 30_000,
    queryFn: async () => {
      const rows = [];
      let offset = 0;
      for (let pageCount = 0; pageCount < 10; pageCount += 1) {
        const { data, error } = await apiClient.GET("/api/v1/runs", {
          params: { query: { limit: 100, offset, sort: "-created_at" } },
        });
        if (error) throw new Error(requestErrorMessage(error));
        if (!data) throw new Error("실행 검색 응답이 비어 있습니다.");
        rows.push(...data.data);
        if (!data.page.has_more) break;
        offset += data.page.limit;
      }
      return rows;
    },
  });

  useEffect(() => {
    if (!open) {
      setSearch("");
    }
  }, [open]);

  const normalized = search.trim().toLowerCase();
  const visible = commands.filter(
    (command) =>
      !normalized ||
      `${command.label} ${command.description}`.toLowerCase().includes(normalized),
  );
  const matchingRuns = (runs.data ?? [])
    .filter((run) =>
      `${run.run_id} ${run.run_name}`.toLowerCase().includes(normalized),
    )
    .slice(0, 6);

  function submitSearch() {
    if (!normalized) return;
    const exactRun = (runs.data ?? []).find(
      (run) =>
        run.run_id.toLowerCase() === normalized ||
        run.run_name.toLowerCase() === normalized,
    );
    if (exactRun) {
      navigate(`/runs/${encodeURIComponent(exactRun.run_id)}`);
      onOpenChange(false);
      return;
    }
    updateFilters({ symbol: search.trim().toUpperCase() });
    navigate("/runs");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <div>
          <DialogTitle>명령 팔레트</DialogTitle>
          <DialogDescription>
            구획을 이동하거나 run_id·run_name을 열고 심볼로 카탈로그를 좁힙니다.
          </DialogDescription>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submitSearch();
            }}
            autoFocus
            placeholder="명령, run_id, run_name 또는 심볼 검색…"
            className="pl-9"
          />
        </div>
        <div className="space-y-1">
          {visible.map((command) => {
            const Icon = command.icon;
            return (
              <button
                key={command.label}
                type="button"
                disabled={!command.path}
                onClick={() => {
                  if (!command.path) return;
                  navigate(command.path);
                  onOpenChange(false);
                }}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Icon className="h-4 w-4 text-teal-400" />
                <span className="flex-1">
                  <span className="block text-sm font-medium">{command.label}</span>
                  <span className="block text-xs text-muted-foreground">
                    {command.description}
                  </span>
                </span>
              </button>
            );
          })}
          {normalized && matchingRuns.length > 0 && (
            <div className="border-t pt-2">
              <p className="px-3 pb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                실행 검색
              </p>
              {matchingRuns.map((run) => (
                <button
                  key={run.run_id}
                  type="button"
                  onClick={() => {
                    navigate(`/runs/${encodeURIComponent(run.run_id)}`);
                    onOpenChange(false);
                  }}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-accent"
                >
                  <Search className="h-4 w-4 text-teal-400" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {run.run_name}
                    </span>
                    <span className="block truncate font-mono text-[10px] text-muted-foreground">
                      {run.run_id}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
          {normalized && (
            <button
              type="button"
              onClick={submitSearch}
              className="flex w-full items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2.5 text-left hover:bg-primary/10"
            >
              <Search className="h-4 w-4 text-teal-400" />
              <span className="text-sm">
                심볼 <strong>{search.trim().toUpperCase()}</strong> 검색
              </span>
              <kbd className="ml-auto text-xs text-muted-foreground">Enter</kbd>
            </button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

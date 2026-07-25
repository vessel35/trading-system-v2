import {
  BarChart3,
  BookOpenCheck,
  FlaskConical,
  LayoutList,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "wouter";

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
    label: "Evidence 분석",
    description: "P1에서 활성화",
    path: null,
    icon: BarChart3,
  },
  {
    label: "실행 관리",
    description: "P2 dry-run 관리에서 활성화",
    path: null,
    icon: FlaskConical,
  },
  {
    label: "전략",
    description: "전략 레지스트리 참조 예정",
    path: null,
    icon: BookOpenCheck,
  },
] as const;

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const [, navigate] = useLocation();
  const { updateFilters } = useCatalogFilters();
  const [search, setSearch] = useState("");

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

  function submitSearch() {
    if (!normalized) return;
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
            구획을 이동하거나 심볼로 카탈로그를 바로 좁힙니다.
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
            placeholder="명령 또는 심볼 검색…"
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

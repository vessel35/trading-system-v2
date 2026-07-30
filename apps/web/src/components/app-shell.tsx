import {
  Activity,
  BarChart3,
  BookOpenCheck,
  ChevronRight,
  Database,
  FlaskConical,
  LayoutList,
  LockKeyhole,
  Moon,
  Search,
  Settings2,
  ShieldAlert,
  Sun,
  X,
} from "lucide-react";
import { type PropsWithChildren, useEffect, useState } from "react";
import { Link, useLocation } from "wouter";

import { useCatalogFilters } from "../contexts/catalog-filters";
import { useComparisonBasket } from "../contexts/comparison-basket";
import { cn } from "../lib/utils";
import { CommandPalette } from "./command-palette";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

const researchNav = [
  { label: "카탈로그", icon: LayoutList, path: "/runs", enabled: true },
  { label: "분석", icon: BarChart3, path: "/compare", enabled: true },
  { label: "실행 관리", icon: FlaskConical, path: "/manage", enabled: true },
  { label: "데이터", icon: Database, path: "/data", enabled: true },
  { label: "전략", icon: BookOpenCheck, path: "/strategies", enabled: false },
] as const;

const liveNav = [
  { label: "모니터", icon: Activity },
  { label: "제어", icon: ShieldAlert },
] as const;

export function AppShell({ children }: PropsWithChildren) {
  const [location, navigate] = useLocation();
  const { items, remove, clear } = useComparisonBasket();
  const { activeCount } = useCatalogFilters();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [basketOpen, setBasketOpen] = useState(false);
  const [dark, setDark] = useState(true);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function toggleTheme() {
    setDark((current) => {
      const next = !current;
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  }

  return (
    <div className="min-h-screen">
      <header className="fixed inset-x-0 top-0 z-40 flex h-14 items-center border-b bg-background/90 px-4 backdrop-blur-xl">
        <button
          type="button"
          onClick={() => navigate("/runs")}
          className="flex min-w-52 items-center gap-2.5 text-left"
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg border border-primary/25 bg-primary/10 text-teal-300">
            <BarChart3 className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-sm font-semibold leading-tight">Backtest Console</span>
            <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Research workspace
            </span>
          </span>
        </button>

        <div className="ml-5 hidden items-center gap-2 md:flex">
          <Badge>RESEARCH</Badge>
          <Badge variant="outline" className="border-teal-500/20 text-teal-200">
            DRY-RUN
          </Badge>
        </div>

        <div className="ml-auto flex items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPaletteOpen(true)}
            className="hidden min-w-52 justify-start text-muted-foreground md:flex"
          >
            <Search className="mr-2 h-3.5 w-3.5" />
            명령·심볼 검색
            <kbd className="ml-auto rounded border bg-muted px-1.5 font-sans text-[10px]">⌘K</kbd>
          </Button>
          {activeCount > 0 && (
            <Badge variant="secondary" className="hidden sm:flex">
              필터 {activeCount}
            </Badge>
          )}
          <Button
            variant={items.length > 0 ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setBasketOpen((current) => !current)}
          >
            <Settings2 className="mr-1.5 h-3.5 w-3.5" />
            비교 ({items.length})
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label="테마 전환"
          >
            {dark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      <aside className="fixed bottom-0 left-0 top-14 z-30 hidden w-56 border-r bg-card/55 px-3 py-5 backdrop-blur lg:block">
        <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
          연구
        </div>
        <nav className="space-y-1">
          {researchNav.map((item) => {
            const Icon = item.icon;
            if (!item.enabled) {
              return (
                <div
                  key={item.label}
                  className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground/45"
                  title="후속 단계에서 활성화"
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                  <LockKeyhole className="ml-auto h-3 w-3" />
                </div>
              );
            }
            return (
              <Link
                key={item.label}
                href={item.path}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  location.startsWith(item.path)
                    ? "bg-primary/10 text-teal-200"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
                <ChevronRight className="ml-auto h-3 w-3 opacity-50" />
              </Link>
            );
          })}
        </nav>

        <div className="my-5 border-t border-red-500/15" />
        <div className="mb-2 flex items-center gap-2 px-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-red-300/60">
          라이브
          <LockKeyhole className="h-3 w-3" />
        </div>
        <nav className="space-y-1">
          {liveNav.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-red-200/30"
                title="별도 라이브 프리셋 확정 전 비활성"
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
                <LockKeyhole className="ml-auto h-3 w-3" />
              </div>
            );
          })}
        </nav>

        <div className="absolute bottom-5 left-3 right-3 rounded-lg border border-teal-500/10 bg-teal-500/5 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-teal-200">
            <LockKeyhole className="h-3.5 w-3.5" />
            dry-run 격리
          </div>
          <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">
            조회는 읽기 전용이며 트리거는 카탈로그·Evidence만 생성합니다. 주문·지갑 경로는 없습니다.
          </p>
        </div>
      </aside>

      <main className="pt-14 lg:pl-56">
        {children}
      </main>

      {basketOpen && (
        <div className="fixed right-4 top-16 z-50 w-[calc(100%-2rem)] max-w-sm rounded-xl border bg-card p-4 shadow-2xl">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">비교 바스켓</h2>
              <p className="text-xs text-muted-foreground">
                두 실행 이상이면 저장 지표와 설정을 비교합니다.
              </p>
            </div>
            <Button variant="ghost" size="icon" onClick={() => setBasketOpen(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-3 space-y-2">
            {items.length === 0 ? (
              <div className="rounded-lg border border-dashed p-6 text-center text-xs text-muted-foreground">
                카탈로그에서 실행을 선택해 담으세요.
              </div>
            ) : (
              items.map((item) => (
                <div
                  key={item.run_id}
                  className="flex items-center gap-3 rounded-lg border bg-background/50 p-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium">{item.run_name}</p>
                    <p className="truncate text-[10px] text-muted-foreground">
                      {item.strategy_name} · {item.symbol} · {item.timeframe}
                    </p>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => remove(item.run_id)}>
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))
            )}
          </div>
          {items.length > 0 && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Button variant="ghost" size="sm" onClick={clear}>
                바스켓 비우기
              </Button>
              <Button
                size="sm"
                disabled={items.length < 2}
                onClick={() => {
                  setBasketOpen(false);
                  navigate("/compare");
                }}
              >
                비교 열기
              </Button>
            </div>
          )}
        </div>
      )}

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { CatalogFilterProvider } from "../contexts/catalog-filters";
import { ComparisonBasketProvider } from "../contexts/comparison-basket";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { CatalogPage } from "./catalog-page";

interface StoredRun {
  run_id: string;
  run_name: string;
  deleted_at: string | null;
}

function runRow(stored: StoredRun) {
  return {
    run_id: stored.run_id,
    run_name: stored.run_name,
    status: "EVALUATED",
    strategy_id: "vessel-reference",
    strategy_name: "VesselReference",
    symbol: "BTC/USDT:USDT",
    exchange: "binance",
    timeframe: "1h",
    market_type: "FUTURES",
    period_start: "2025-01-01T00:00:00Z",
    period_end: "2025-02-01T00:00:00Z",
    created_at: "2025-02-02T00:00:00Z",
    sweep_id: null,
    config_hash: "0".repeat(64),
    trade_count: 41,
    pf: 1.8,
    sortino: 1.3,
    calmar_or_mar: 1.1,
    sqn: 1.9,
    mdd: -0.11,
    ror: 0,
    win_rate: 0.44,
    net_pnl_total: "1840.12",
    gate_verdict: "pass",
    decision_route: "promote",
    integrity_status: "passed",
    data_coverage_ratio: 1,
    summary_present: true,
    deleted_at: stored.deleted_at,
  };
}

/** A catalog whose delete marker actually moves, so the list can be re-read. */
function catalogServer(initial: StoredRun[]) {
  const runs = new Map(initial.map((run) => [run.run_id, { ...run }]));
  const requestedFilters: string[] = [];
  const purged: string[] = [];

  server.use(
    http.get("*/api/v1/tags/facets", () => HttpResponse.json({ data: [] })),
    http.get("*/api/v1/runs", ({ request }) => {
      const deleted = new URL(request.url).searchParams.get("deleted") ?? "exclude";
      requestedFilters.push(deleted);
      const visible = [...runs.values()].filter((run) => {
        if (deleted === "only") return run.deleted_at !== null;
        if (deleted === "include") return true;
        return run.deleted_at === null;
      });
      return HttpResponse.json({
        data: visible.map(runRow),
        page: { limit: 50, offset: 0, total: visible.length, has_more: false },
      });
    }),
    http.delete("*/api/v1/runs/:runIdWithVerb", ({ params }) => {
      const raw = String(params.runIdWithVerb);
      const purging = raw.endsWith(":purge");
      const runId = raw.replace(/:purge$/, "");
      const run = runs.get(runId);
      if (!run) return new HttpResponse(null, { status: 404 });
      if (purging) {
        runs.delete(runId);
        purged.push(runId);
        return HttpResponse.json({
          run_id: runId,
          run_removed: true,
          evidence_removed: true,
          evidence_path: `${runId}.sqlite`,
        });
      }
      run.deleted_at = "2026-07-31T00:00:00Z";
      return HttpResponse.json({
        run_id: run.run_id,
        deleted: true,
        deleted_at: run.deleted_at,
        changed: true,
      });
    }),
    http.post("*/api/v1/runs/:runIdWithVerb", ({ params }) => {
      const runId = String(params.runIdWithVerb).replace(/:restore$/, "");
      const run = runs.get(runId);
      if (!run) return new HttpResponse(null, { status: 404 });
      run.deleted_at = null;
      return HttpResponse.json({
        run_id: runId,
        deleted: false,
        deleted_at: null,
        changed: true,
      });
    }),
  );
  return { runs, requestedFilters, purged };
}

function renderCatalog() {
  return renderWithQuery(
    <CatalogFilterProvider>
      <ComparisonBasketProvider>
        <CatalogPage />
      </ComparisonBasketProvider>
    </CatalogFilterProvider>,
  );
}

/**
 * Wait for a run name to be listed, then hand back nothing: the first render
 * after the query settles replaces the row nodes, so every later query must be
 * made fresh rather than held across an await.
 */
async function listed(runName: string) {
  await screen.findByText(runName);
}

describe("카탈로그 실행 삭제 표시", () => {
  it("확인을 거쳐 삭제하면 기본 목록에서 사라지고 저장물은 남는다는 것을 알린다", async () => {
    const user = userEvent.setup();
    const catalog = catalogServer([
      { run_id: "BT_1", run_name: "alpha", deleted_at: null },
      { run_id: "BT_2", run_name: "beta", deleted_at: null },
    ]);
    renderCatalog();

    await listed("alpha");
    await user.click(screen.getByRole("button", { name: "alpha 삭제" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("실행 1개를 삭제할까요?")).toBeInTheDocument();
    expect(within(dialog).getByText(/증거 파일은 그대로 남으며/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "삭제" }));

    await waitFor(() => expect(screen.queryByText("alpha")).not.toBeInTheDocument());
    expect(screen.getByText("beta")).toBeInTheDocument();
    expect(catalog.runs.get("BT_1")?.deleted_at).not.toBeNull();
  });

  it("취소하면 아무 것도 삭제하지 않는다", async () => {
    const user = userEvent.setup();
    const catalog = catalogServer([
      { run_id: "BT_1", run_name: "alpha", deleted_at: null },
    ]);
    renderCatalog();

    await listed("alpha");
    await user.click(screen.getByRole("button", { name: "alpha 삭제" }));
    await screen.findByRole("dialog");
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "취소" }),
    );

    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(catalog.runs.get("BT_1")?.deleted_at).toBeNull();
  });

  it("삭제만 보기로 바꾸면 삭제된 실행을 찾아 확인 없이 복원한다", async () => {
    const user = userEvent.setup();
    const catalog = catalogServer([
      { run_id: "BT_1", run_name: "alpha", deleted_at: "2026-07-30T00:00:00Z" },
      { run_id: "BT_2", run_name: "beta", deleted_at: null },
    ]);
    renderCatalog();

    await listed("beta");
    expect(screen.queryByText("alpha")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("삭제 표시 필터"), "only");
    await listed("alpha");
    expect(screen.queryByText("beta")).not.toBeInTheDocument();
    expect(screen.getByText("삭제됨")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "alpha 복원" }));
    await waitFor(() => expect(catalog.runs.get("BT_1")?.deleted_at).toBeNull());
    expect(catalog.requestedFilters).toContain("only");
  });

  it("여러 건을 골라 한 번에 삭제한다", async () => {
    const user = userEvent.setup();
    const catalog = catalogServer([
      { run_id: "BT_1", run_name: "alpha", deleted_at: null },
      { run_id: "BT_2", run_name: "beta", deleted_at: null },
    ]);
    renderCatalog();

    await listed("alpha");
    await user.click(screen.getByLabelText("alpha 선택"));
    await user.click(screen.getByLabelText("beta 선택"));
    await user.click(screen.getByRole("button", { name: /선택 삭제/ }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("실행 2개를 삭제할까요?")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "삭제" }));

    await waitFor(() => {
      expect(catalog.runs.get("BT_1")?.deleted_at).not.toBeNull();
      expect(catalog.runs.get("BT_2")?.deleted_at).not.toBeNull();
    });
    expect(await screen.findByText("조건에 맞는 실행이 없습니다.")).toBeInTheDocument();
  });
});

describe("카탈로그 실행 완전 삭제", () => {
  it("증거 파일까지 지운다고 알린 뒤 목록에서 영구히 없앤다", async () => {
    const user = userEvent.setup();
    const catalog = catalogServer([
      { run_id: "BT_1", run_name: "alpha", deleted_at: null },
      { run_id: "BT_2", run_name: "beta", deleted_at: null },
    ]);
    renderCatalog();

    await listed("alpha");
    await user.click(screen.getByLabelText("alpha 선택"));
    await user.click(screen.getByRole("button", { name: /선택 완전 삭제/ }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText("실행 1개를 완전히 삭제할까요?"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/증거 SQLite 파일까지 지웁니다/)).toBeInTheDocument();
    expect(within(dialog).getByText(/되돌릴 수 없고/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "완전 삭제" }));

    await waitFor(() => expect(catalog.purged).toEqual(["BT_1"]));
    expect(catalog.runs.has("BT_1")).toBe(false);
    await waitFor(() => expect(screen.queryByText("alpha")).not.toBeInTheDocument());
    expect(screen.getByText("beta")).toBeInTheDocument();
  });

  it("이미 삭제 표시된 실행도 골라 완전 삭제할 수 있다", async () => {
    const user = userEvent.setup();
    const catalog = catalogServer([
      { run_id: "BT_1", run_name: "alpha", deleted_at: "2026-07-30T00:00:00Z" },
      { run_id: "BT_2", run_name: "beta", deleted_at: "2026-07-30T00:00:00Z" },
    ]);
    renderCatalog();

    await user.selectOptions(screen.getByLabelText("삭제 표시 필터"), "only");
    await listed("alpha");
    await user.click(screen.getByLabelText("alpha 선택"));
    await user.click(screen.getByLabelText("beta 선택"));
    await user.click(screen.getByRole("button", { name: /선택 완전 삭제/ }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText("실행 2개를 완전히 삭제할까요?"),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "완전 삭제" }));

    await waitFor(() => expect(catalog.purged).toEqual(["BT_1", "BT_2"]));
    expect(catalog.runs.size).toBe(0);
    expect(await screen.findByText("조건에 맞는 실행이 없습니다.")).toBeInTheDocument();
  });

  it("취소하면 아무 것도 지우지 않는다", async () => {
    const user = userEvent.setup();
    const catalog = catalogServer([
      { run_id: "BT_1", run_name: "alpha", deleted_at: null },
    ]);
    renderCatalog();

    await listed("alpha");
    await user.click(screen.getByLabelText("alpha 선택"));
    await user.click(screen.getByRole("button", { name: /선택 완전 삭제/ }));
    await screen.findByRole("dialog");
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "취소" }),
    );

    expect(catalog.purged).toEqual([]);
    expect(catalog.runs.has("BT_1")).toBe(true);
    expect(screen.getByText("alpha")).toBeInTheDocument();
  });
});

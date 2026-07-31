import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ComparisonBasketProvider } from "../contexts/comparison-basket";
import { summaryHelpBySection } from "../lib/summary-help";
import { renderWithQuery } from "../test/render";
import { RunSummaryPage } from "./run-summary-page";

const runFixture = {
  run_id: "help-run",
  run_name: "help",
  status: "EVALUATED",
  strategy_id: "fixture-strategy",
  strategy_name: "Fixture",
  strategy_version: "1",
  symbol: "BTC/USDT:USDT",
  exchange: "binance",
  timeframe: "1h",
  market_type: "futures",
  period_start: "2025-01-01T00:00:00Z",
  period_end: "2025-02-01T00:00:00Z",
  created_at: "2025-02-02T00:00:00Z",
  initial_capital: "10000",
  sizing_method: "risk_based",
  risk_per_trade: "0.01",
  position_size_pct: null,
  seed: 7,
  engine_version: "fixture",
  config_hash: "config-hash",
  source_data_hash: "source-hash",
  sweep_id: null,
  fold_label: null,
  data_source: "fixture",
  core_lib_version: "fixture",
  error_message: null,
};

const summaryFixture = {
  run_status: "EVALUATED",
  summary_status: "available",
  summary: {
    run_id: "help-run",
    pf: 1.82,
    sortino: 1.35,
    calmar_or_mar: 1.1,
    sqn: 1.94,
    mdd: -0.11,
    ror: 0.0,
    sharpe: 1.02,
    win_rate: 0.44,
    payoff: 2.3,
    expectancy_r: 0.31,
    ulcer: 3.4,
    kelly: 0.19,
    trade_count: 41,
    win_count: 18,
    loss_count: 23,
    r_excluded_count: 0,
    annualization: "daily_resample_sqrt365",
    initial_capital: "10000",
    final_equity: "11840.12",
    net_pnl_total: "1840.12",
    gross_pnl_total: "1980.44",
    total_fee: "96.21",
    total_slippage: "38.11",
    total_funding: "6.00",
    total_liquidation_penalty: "0",
    integrity_passed: true,
    integrity_status: "passed",
    integrity_failed_json: null,
    gate_passed: true,
    gate_stage: "B",
    gate_verdict: "pass",
    gate_failed_json: null,
    envelope_result: "in_range",
    envelope_deviated_json: null,
    decision_route: "promote",
    decision_rationale: "pf: met the preregistered success threshold",
    oos_degradation: null,
    psr: null,
    harness_json: null,
    computed_at: "2025-02-02T00:00:00Z",
    expected_candle_count: 744,
    observed_candle_count: 744,
    source_absent_gap_count: 0,
    partial_bucket_count: 0,
    data_coverage_ratio: 1,
    max_consecutive_gap_bars: 0,
    max_consecutive_gap_seconds: 0,
    data_coverage_passed: true,
    unobservable_funding_boundary_count: 0,
    data_gap_exit_count: 0,
  },
};

function successfulQuery<T>(data: T) {
  return { data, error: null, isError: false, isLoading: false };
}

vi.mock("../hooks/use-catalog", () => ({
  useRun: () => successfulQuery(runFixture),
  useRunSummary: () => successfulQuery(summaryFixture),
  useSetRunDeleted: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("../hooks/use-evidence", () => ({
  useTrades: () => successfulQuery([]),
}));

vi.mock("../components/run-tags", () => ({
  RunTags: () => <output>태그 영역</output>,
}));

vi.mock("../components/evidence/trade-drawer", () => ({
  TradeDrawer: () => null,
}));

function renderPage() {
  return renderWithQuery(
    <ComparisonBasketProvider>
      <RunSummaryPage runId="help-run" />
    </ComparisonBasketProvider>,
  );
}

describe("백테스트 세부 정보 값 도움말", () => {
  it("지표 타일의 물음표가 그 지표의 뜻·읽는 법·통과 기준을 연다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "SQN 설명 보기" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("핵심 지표 도움말")).toBeInTheDocument();
    const entry = within(dialog)
      .getByRole("heading", { name: "SQN", level: 3 })
      .closest("article");
    expect(entry).not.toBeNull();
    expect(entry).toHaveAttribute("data-focused", "true");
    expect(entry).toHaveTextContent("시스템 품질 지수");
    expect(entry).toHaveTextContent("거래가 30건 미만이면");
    expect(entry).toHaveTextContent("1.6 이상");
  });

  it("건강도와 비용은 각자의 도움말을 열고 지표 도움말과 섞이지 않는다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Coverage 설명 보기" }));
    const healthDialog = await screen.findByRole("dialog");
    expect(
      within(healthDialog).getByText("데이터 건강도 도움말"),
    ).toBeInTheDocument();
    expect(within(healthDialog).getByText("95% 이상")).toBeInTheDocument();
    expect(within(healthDialog).queryByRole("heading", { name: "PF" })).toBeNull();

    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Funding 설명 보기" }));
    const costDialog = await screen.findByRole("dialog");
    expect(within(costDialog).getByText("비용 분해 도움말")).toBeInTheDocument();
    const funding = within(costDialog)
      .getByRole("heading", { name: "Funding", level: 3 })
      .closest("article");
    expect(funding).toHaveAttribute("data-focused", "true");
    expect(funding).toHaveTextContent("음수이면 오히려 받은 금액");
  });

  it("카드 머리말의 도움말은 어느 항목도 지목하지 않고 전체를 보여 준다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "핵심 지표 도움말" }));

    const dialog = await screen.findByRole("dialog");
    for (const item of summaryHelpBySection.metrics.items) {
      expect(
        within(dialog).getByRole("heading", { name: item.label, level: 3 }),
      ).toBeInTheDocument();
    }
    expect(dialog.querySelector("[data-focused]")).toBeNull();
  });

  it("판정 배지마다 그 값이 무엇을 뜻하는지 열 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "ROUTE 설명 보기" }));

    const dialog = await screen.findByRole("dialog");
    const route = within(dialog)
      .getByRole("heading", { name: "ROUTE", level: 3 })
      .closest("article");
    expect(route).toHaveAttribute("data-focused", "true");
    expect(route).toHaveTextContent("promote는 성공 기준을 넘어");
    expect(route).toHaveTextContent("abandon은 실패 기준에 걸렸고");
  });
});

describe("도움말 본문 규약", () => {
  it("모든 항목이 뜻·읽는 법·통과 기준을 빠짐없이 갖는다", () => {
    for (const section of Object.values(summaryHelpBySection)) {
      expect(section.items.length).toBeGreaterThan(0);
      for (const item of section.items) {
        expect(item.meaning.length).toBeGreaterThan(10);
        expect(item.reading.length).toBeGreaterThan(10);
        expect(item.criterion.length).toBeGreaterThan(0);
      }
    }
  });

  it("항목 식별자가 섹션 안에서 중복되지 않는다", () => {
    for (const section of Object.values(summaryHelpBySection)) {
      const ids = section.items.map((item) => item.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
  });
});

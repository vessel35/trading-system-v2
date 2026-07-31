import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ComparisonBasketProvider } from "../contexts/comparison-basket";
import { renderWithQuery } from "../test/render";
import { RunSummaryPage } from "./run-summary-page";

const runFixture = {
  run_id: "fixture-run",
  run_name: "fixture",
  status: "EVALUATED",
  strategy_id: "fixture-strategy",
  strategy_name: "Fixture",
  strategy_version: "1",
  symbol: "BTC/USDT:USDT",
  exchange: "binance",
  timeframe: "1h",
  market_type: "futures",
  period_start: "2025-01-01T00:00:00Z",
  period_end: "2025-01-02T00:00:00Z",
  created_at: "2025-01-03T00:00:00Z",
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
  summary_status: "missing",
  summary: null,
};

function successfulQuery<T>(data: T) {
  return {
    data,
    error: null,
    isError: false,
    isLoading: false,
  };
}

vi.mock("../hooks/use-catalog", () => ({
  useRun: () => successfulQuery(runFixture),
  useRunSummary: () => successfulQuery(summaryFixture),
  useSetRunDeleted: () => ({ mutate: vi.fn(), isPending: false }),
  usePurgeRun: () => ({ mutate: vi.fn(), isPending: false }),
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

vi.mock("../components/evidence/equity-drawdown-tab", () => ({
  EquityDrawdownTab: () => {
    throw new Error("fixture Evidence tab failure");
  },
}));

vi.mock("../components/evidence/trades-tab", () => ({
  TradesTab: () => <output>거래 탭 정상</output>,
}));

vi.mock("../components/evidence/chart-tab", () => ({
  ChartTab: () => <output>차트 탭 정상</output>,
}));

vi.mock("../components/evidence/signals-decisions-tab", () => ({
  SignalsDecisionsTab: () => <output>신호 탭 정상</output>,
}));

vi.mock("../components/evidence/integrity-cost-tab", () => ({
  IntegrityCostTab: () => <output>무결성 탭 정상</output>,
}));

vi.mock("../components/evidence/research-notes-tab", () => ({
  ResearchNotesTab: () => <output>연구 탭 정상</output>,
}));

describe("RunSummary Evidence 경계 배선", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("한 Evidence 탭의 렌더 예외를 격리해 실행 화면과 다른 탭을 유지한다", async () => {
    const user = userEvent.setup();
    renderWithQuery(
      <ComparisonBasketProvider>
        <RunSummaryPage runId="fixture-run" />
      </ComparisonBasketProvider>,
    );

    expect(screen.getByRole("heading", { name: "fixture-run" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "자본곡선·DD" }));
    expect(
      await screen.findByText("이 Evidence 탭을 표시하지 못했습니다."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "fixture-run" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "개요" }));
    expect(screen.getByText("저장된 요약이 아직 없습니다.")).toBeInTheDocument();
  });
});

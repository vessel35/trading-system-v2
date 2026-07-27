import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { CatalogFilterProvider } from "../contexts/catalog-filters";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { CommandPalette } from "./command-palette";

const catalogFixture = {
  run_id: "run-2025-alpha",
  run_name: "alpha-breakout",
  status: "EVALUATED",
  strategy_id: "vessel-reference",
  strategy_name: "Vessel",
  symbol: "BTC/USDT:USDT",
  exchange: "binance",
  timeframe: "1h",
  market_type: "futures",
  period_start: "2025-01-01T00:00:00Z",
  period_end: "2025-01-02T00:00:00Z",
  created_at: "2025-01-03T00:00:00Z",
  sweep_id: null,
  config_hash: "abc",
  trade_count: 1,
  pf: 1.1,
  sortino: 1.2,
  calmar_or_mar: 1.3,
  sqn: 1.4,
  mdd: 0.1,
  ror: 0,
  win_rate: 0.5,
  net_pnl_total: "1.00",
  gate_verdict: "pass",
  decision_route: "accept",
  integrity_status: "passed",
  data_coverage_ratio: 1,
  summary_present: true,
};

describe("명령 팔레트", () => {
  it("현재 라우트를 활성화하고 run_id·run_name 검색 결과를 연다", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("http://localhost/api/v1/runs", () =>
        HttpResponse.json({
          data: [catalogFixture],
          page: { limit: 100, offset: 0, total: 1, has_more: false },
        }),
      ),
    );
    renderWithQuery(
      <CatalogFilterProvider>
        <CommandPalette open onOpenChange={vi.fn()} />
      </CatalogFilterProvider>,
    );

    expect(
      await screen.findByRole("button", { name: /실행 비교 분석/ }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: /실행 관리/ })).toBeEnabled();

    await user.type(
      screen.getByPlaceholderText("명령, run_id, run_name 또는 심볼 검색…"),
      "alpha-breakout",
    );
    expect(
      await screen.findByRole("button", { name: /alpha-breakout.*run-2025-alpha/ }),
    ).toBeInTheDocument();
  });

  it("1,000건 조회 상한 뒤에도 더 있으면 일부 조회임을 고지한다", async () => {
    server.use(
      http.get("http://localhost/api/v1/runs", ({ request }) => {
        const offset = Number(new URL(request.url).searchParams.get("offset") ?? 0);
        return HttpResponse.json({
          data: Array.from({ length: 100 }, (_, index) => ({
            ...catalogFixture,
            run_id: `run-${offset + index}`,
            run_name: `fixture-${offset + index}`,
          })),
          page: {
            limit: 100,
            offset,
            total: 1_001,
            has_more: true,
          },
        });
      }),
    );
    renderWithQuery(
      <CatalogFilterProvider>
        <CommandPalette open onOpenChange={vi.fn()} />
      </CatalogFilterProvider>,
    );

    const notice = await screen.findByRole("status");
    expect(notice).toHaveTextContent("최근 1,000개 실행까지만");
    expect(notice).toHaveTextContent("카탈로그에서 조건을 좁히세요");
  });
});

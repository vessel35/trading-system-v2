import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { emptyEvidenceFixture } from "../../test/fixtures/evidence";
import { renderWithQuery } from "../../test/render";
import { server } from "../../test/server";
import { SignalsDecisionsTab } from "./signals-decisions-tab";

vi.mock("recharts", () => {
  const Container = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    BarChart: Container,
    CartesianGrid: () => null,
    ResponsiveContainer: Container,
    Tooltip: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Bar: ({
      onClick,
    }: {
      onClick?: (entry: { payload: { name: string } }) => void;
    }) => (
      <button
        type="button"
        onClick={() => onClick?.({ payload: { name: "cooldown" } })}
      >
        blocked_by 막대
      </button>
    ),
  };
});

describe("신호·의사결정 필터", () => {
  it("분포 막대로 설정한 blocked_by 필터를 초기화할 수 있다", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(
        "http://localhost/api/v1/runs/:runId/candidate-events",
        () =>
          HttpResponse.json({
            data: [
              {
                candidate_id: 1,
                run_id: "fixture-filter",
                ts: "2025-01-01T00:00:00Z",
                symbol: "BTC/USDT:USDT",
                trigger_rule: "cross",
                passed_filters_json: {},
                blocked_by: "cooldown",
                would_be_side: "LONG",
                would_be_qty: "1",
                realized: false,
                linked_trade_id: null,
              },
              {
                candidate_id: 2,
                run_id: "fixture-filter",
                ts: "2025-01-01T00:01:00Z",
                symbol: "BTC/USDT:USDT",
                trigger_rule: "cross",
                passed_filters_json: {},
                blocked_by: "risk_limit",
                would_be_side: "LONG",
                would_be_qty: "1",
                realized: false,
                linked_trade_id: null,
              },
            ],
            page: {
              ...emptyEvidenceFixture.page,
              total: 2,
            },
          }),
      ),
    );
    renderWithQuery(
      <SignalsDecisionsTab runId="fixture-filter" onSelectTrade={vi.fn()} />,
    );

    await user.click(await screen.findByRole("button", { name: "blocked_by 막대" }));
    expect(screen.getByRole("tab", { name: "후보 1" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "초기화" }));
    expect(screen.getByRole("tab", { name: "후보 2" })).toBeInTheDocument();
  });
});

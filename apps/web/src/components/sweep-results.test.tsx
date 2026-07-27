import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ComparisonBasketProvider } from "../contexts/comparison-basket";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { SweepResults } from "./sweep-results";

describe("과거 스윕 결과", () => {
  it("현재 세션 TrackedSweep 없이 sweep_id만으로 저장 결과를 조회한다", async () => {
    server.use(
      http.get("http://localhost/api/v1/sweeps/:sweepId", ({ params }) =>
        HttpResponse.json({
          sweep_id: params.sweepId,
          representative_run_id: "representative-run",
          runs: [],
          oos_degradation: null,
          psr: null,
          oos_degradation_limit: 0.2,
          psr_minimum: 0.95,
          harness_json: null,
        }),
      ),
    );
    renderWithQuery(
      <ComparisonBasketProvider>
        <SweepResults sweep={undefined} sweepId="past-sweep" />
      </ComparisonBasketProvider>,
    );

    expect(
      await screen.findByText("스윕 결과 · past-sweep"),
    ).toBeInTheDocument();
  });
});

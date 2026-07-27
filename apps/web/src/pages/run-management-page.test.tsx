import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import type { TrackedJob, TrackedSweep } from "../contexts/run-jobs";
import { RunJobsProvider } from "../contexts/run-jobs";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import {
  JobRow,
  RunManagementPage,
  SweepJobRow,
} from "./run-management-page";

vi.mock("../components/sweep-results", () => ({
  SweepResults: ({ sweepId }: { sweepId?: string | null }) => (
    <output aria-label="열린 스윕">{sweepId ?? ""}</output>
  ),
}));

function managementHandlers() {
  return [
    http.get("http://localhost/api/v1/strategies", () =>
      HttpResponse.json({
        data: [
          {
            strategy_id: "vessel-reference",
            display_name: "Vessel",
            strategy_version: "1",
            supported_timeframes: ["1h"],
            required_indicators: [],
            min_history: 10,
            default_params: {
              reward_risk: 2,
              atr_stop_multiple: 1.5,
            },
            is_active: true,
            is_deprecated: false,
            source: "strategy_registry",
          },
        ],
      }),
    ),
    http.get(
      "http://localhost/api/v1/data-sources/:dataSource/coverage",
      () =>
        HttpResponse.json({
          data_source: "crypto_data.ohlcv_futures",
          symbol: "BTC/USDT:USDT",
          exchange: "binance",
          source_timeframe: "1m",
          available_from: "2025-01-01T00:00:00Z",
          available_to: "2026-01-01T00:00:00Z",
          row_count: 1_000_000,
          expected_1m_rows: 1_000_000,
          missing_1m_rows: 0,
        }),
    ),
  ];
}

function renderManagement() {
  server.use(...managementHandlers());
  return renderWithQuery(
    <RunJobsProvider>
      <RunManagementPage />
    </RunJobsProvider>,
  );
}

describe("실행 관리 보강", () => {
  it("트리거와 스윕 버튼 모두 HTML 폼 검증을 우회하지 않는다", async () => {
    const user = userEvent.setup();
    const runPost = vi.fn();
    const sweepPost = vi.fn();
    server.use(
      ...managementHandlers(),
      http.post("http://localhost/api/v1/runs", () => {
        runPost();
        return HttpResponse.json({}, { status: 500 });
      }),
      http.post("http://localhost/api/v1/sweeps", () => {
        sweepPost();
        return HttpResponse.json({}, { status: 500 });
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );

    const runName = await screen.findByLabelText(/실행 이름/);
    await user.clear(runName);
    await user.type(runName, "Invalid Name");
    expect(runName).toBeInvalid();

    await user.click(screen.getByRole("button", { name: "트리거(모의)" }));
    await user.click(screen.getByRole("button", { name: "스윕 트리거(모의)" }));
    expect(runPost).not.toHaveBeenCalled();
    expect(sweepPost).not.toHaveBeenCalled();
  });

  it("사이징 입력에 계약 범위의 min/max 제약을 둔다", async () => {
    const user = userEvent.setup();
    renderManagement();

    const risk = await screen.findByLabelText(/risk_per_trade/);
    expect(risk).toHaveAttribute("min", "0.000000000001");
    expect(risk).toHaveAttribute("max", "0.01");

    await user.selectOptions(screen.getByLabelText("사이징"), "pct");
    const position = screen.getByLabelText(/position_size_pct/);
    expect(position).toHaveAttribute("min", "0.000000000001");
    expect(position).toHaveAttribute("max", "1");
  });

  it("수치가 없는 RUNNING 상태를 완료율 없는 무기한 표시자로 렌더한다", () => {
    const tracked = {
      accepted: {
        job_id: "job-running",
        status: "QUEUED",
        events_url: "/events",
        status_url: "/status",
      },
      status: {
        job_id: "job-running",
        status: "RUNNING",
        updated_at: "2025-01-01T00:00:00Z",
      },
      submission: {
        config: { run_name: "running-fixture" },
      },
      submittedAt: "2025-01-01T00:00:00Z",
    } as TrackedJob;

    renderWithQuery(<JobRow job={tracked} onEdit={vi.fn()} />);

    const progress = screen.getByRole("progressbar", { name: "실행 중" });
    expect(progress).not.toHaveAttribute("aria-valuenow");
    expect(progress).toHaveAttribute(
      "aria-valuetext",
      "서버 수치 진행률 미제공",
    );
    expect(
      screen.getByText(/완료율은 표시하지 않습니다/),
    ).toBeInTheDocument();
  });

  it("수치가 없는 RUNNING 스윕도 완료율 없는 무기한 표시자로 렌더한다", () => {
    const tracked = {
      accepted: {
        job_id: "sweep-running",
        status: "QUEUED",
        events_url: "/events",
        status_url: "/status",
      },
      status: {
        job_id: "sweep-running",
        status: "RUNNING",
        updated_at: "2025-01-01T00:00:00Z",
      },
      submission: {
        type: "grid",
        config: { run_name: "sweep-fixture" },
      },
      submittedAt: "2025-01-01T00:00:00Z",
    } as TrackedSweep;

    renderWithQuery(
      <SweepJobRow sweep={tracked} onSelectResult={vi.fn()} />,
    );

    const progress = screen.getByRole("progressbar", { name: "스윕 실행 중" });
    expect(progress).not.toHaveAttribute("aria-valuenow");
    expect(progress).toHaveAttribute(
      "aria-valuetext",
      "서버 수치 진행률 미제공",
    );
    expect(
      screen.getByText(/완료율은 표시하지 않습니다/),
    ).toBeInTheDocument();
  });

  it("URL의 sweep_id로 과거 스윕 조회 진입 경로를 복원한다", async () => {
    window.history.replaceState(null, "", "/manage?sweep_id=past-sweep");
    renderManagement();

    expect(await screen.findByLabelText("스윕 ID")).toHaveValue("past-sweep");
    expect(screen.getByLabelText("열린 스윕")).toHaveTextContent("past-sweep");
  });

  it("사전등록 잠금 기능을 쓰기 엔드포인트 미구현 3차 유보로 명시한다", async () => {
    renderManagement();

    expect(
      await screen.findByText(/사전등록 잠금은 쓰기 엔드포인트 미구현으로 유보\(3차\)/),
    ).toBeInTheDocument();
  });
});

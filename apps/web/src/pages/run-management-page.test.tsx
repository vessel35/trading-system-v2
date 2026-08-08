import { screen, waitFor, within } from "@testing-library/react";
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

function managementHandlers(
  supportedTimeframes = ["1h"],
  moneyManagement: {
    supported: string[];
    default: Record<string, unknown>;
  } = {
    supported: ["manual", "turtle"],
    default: {
      mode: "manual",
      leverage: 1,
      reward_risk: 2,
      atr_stop_multiple: 1.5,
    },
  },
) {
  return [
    http.get("http://localhost/api/v1/strategies", () =>
      HttpResponse.json({
        data: [
          {
            strategy_id: "vessel-reference",
            display_name: "Vessel",
            strategy_version: "1",
            supported_timeframes: supportedTimeframes,
            required_indicators: [],
            min_history: 10,
            default_params: {
              reward_risk: 2,
              atr_stop_multiple: 1.5,
            },
            supported_money_management: moneyManagement.supported,
            default_money_management: moneyManagement.default,
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
  it("연구 가설 도움말에서 사전등록 개념과 필드를 확인하고 Esc로 닫는다", async () => {
    const user = userEvent.setup();
    renderManagement();

    await user.click(
      await screen.findByRole("button", { name: "연구 가설 도움말" }),
    );

    const dialog = screen.getByRole("dialog", {
      name: "연구 가설(사전등록) 도움말",
    });
    expect(within(dialog).getByText(/사후 합리화/)).toBeInTheDocument();
    expect(within(dialog).getByText("가설")).toBeInTheDocument();
    expect(within(dialog).getByText("주지표")).toBeInTheDocument();
    expect(within(dialog).getByText("방향")).toBeInTheDocument();
    expect(within(dialog).getByText(/잠금.*미구현·유보/)).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("스윕 설정 도움말이 세 유형을 각각 예로 설명하고 닫기 버튼으로 닫는다", async () => {
    const user = userEvent.setup();
    renderManagement();

    await user.click(await screen.findByText("스윕 설정"));
    await user.click(
      await screen.findByRole("button", { name: "스윕 설정 도움말" }),
    );

    const dialog = screen.getByRole("dialog", {
      name: "스윕 설정 도움말",
    });
    // 유형을 고르는 것이 어려운 부분이므로 세 유형에 각각 풀어 쓴 예가 있어야 한다.
    const examples = within(dialog).getByLabelText("유형별 예시");
    expect(within(examples).getByText(/^grid —/)).toBeInTheDocument();
    expect(within(examples).getByText(/^walk_forward —/)).toBeInTheDocument();
    expect(within(examples).getByText(/^is_oos —/)).toBeInTheDocument();
    // 각 예는 숫자로 무슨 일이 일어나는지 말해야 한다.
    expect(within(examples).getByText(/3×2=6가지 조합/)).toBeInTheDocument();
    expect(within(examples).getByText(/folds=3/)).toBeInTheDocument();
    expect(within(examples).getByText(/split=0\.7/)).toBeInTheDocument();

    expect(within(dialog).getByText(/과적합\(overfitting\)/)).toBeInTheDocument();
    expect(within(dialog).getByText(/OOS 재검증/)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "닫기" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("수동 자금 관리 도움말에서 의미·계산식·예시를 확인하고 Esc와 닫기로 종료한다", async () => {
    const user = userEvent.setup();
    renderManagement();

    const helpButton = await screen.findByRole("button", {
      name: "수동 자금 관리 도움말",
    });
    await user.click(helpButton);

    let dialog = screen.getByRole("dialog", {
      name: "수동 자금 관리 도움말 · Vessel Reference",
    });
    expect(within(dialog).getByText("atr_stop_multiple")).toBeInTheDocument();
    expect(within(dialog).getByText("reward_risk")).toBeInTheDocument();
    expect(within(dialog).getByText("leverage")).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "손절폭(stop_distance) = ATR(14) × atr_stop_multiple",
      ),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "롱 청산가 = 진입가 × (1 − 1/leverage + mmr)",
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/롱 손절가 = .*41,000/)).toBeInTheDocument();
    expect(within(dialog).getByText(/롱 목표가 = .*44,000/)).toBeInTheDocument();
    expect(within(dialog).getByText(/청산가 = .*≈ 28,210/)).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(helpButton);
    dialog = screen.getByRole("dialog", {
      name: "수동 자금 관리 도움말 · Vessel Reference",
    });
    await user.click(within(dialog).getByRole("button", { name: "닫기" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

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

    const symbol = await screen.findByLabelText("심볼");
    await user.clear(symbol);
    expect(symbol).toBeInvalid();

    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
    expect(runPost).not.toHaveBeenCalled();

    // The same submit serves the sweep, so the invalid field must block it too.
    await user.click(await screen.findByText("스윕 설정"));
    await user.click(screen.getByLabelText(/스윕으로 실행/));
    await user.click(screen.getByRole("button", { name: "스윕 실행" }));
    expect(sweepPost).not.toHaveBeenCalled();
  });

  it("스윕 체크가 실행 방식을 정하고 꺼져 있으면 단일 실행만 보낸다", async () => {
    const user = userEvent.setup();
    const runPost = vi.fn();
    const sweepPost = vi.fn();
    server.use(
      http.post("http://localhost/api/v1/runs", () => {
        runPost();
        return HttpResponse.json({}, { status: 500 });
      }),
      http.post("http://localhost/api/v1/sweeps", () => {
        sweepPost();
        return HttpResponse.json({}, { status: 500 });
      }),
    );
    renderManagement();

    // Collapsed, the summary still says which way the run will go.
    const section = await screen.findByText("스윕 설정");
    expect(section.textContent).toMatch(/꺼짐/);

    // Sweep off: the settings below are ignored and one backtest is submitted.
    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
    await waitFor(() => expect(runPost).toHaveBeenCalledTimes(1));
    expect(sweepPost).not.toHaveBeenCalled();

    // Sweep on: the one submit becomes the sweep, and the summary says so.
    await user.click(section);
    await user.click(screen.getByLabelText(/스윕으로 실행/));
    expect(section.textContent).toMatch(/켜짐/);
    await user.click(screen.getByRole("button", { name: "스윕 실행" }));
    await waitFor(() => expect(sweepPost).toHaveBeenCalledTimes(1));
    expect(runPost).toHaveBeenCalledTimes(1);
  });

  it("사이징 입력에 계약 범위의 min/max 제약을 둔다", async () => {
    const user = userEvent.setup();
    renderManagement();

    await user.click(await screen.findByText("고급 실행 가정"));
    const risk = await screen.findByLabelText(/risk_per_trade/);
    expect(risk).toHaveAttribute("min", "0.000000000001");
    expect(risk).toHaveAttribute("max", "0.01");

    await user.selectOptions(screen.getByLabelText("사이징"), "pct");
    const position = screen.getByLabelText(/position_size_pct/);
    expect(position).toHaveAttribute("min", "0.000000000001");
    expect(position).toHaveAttribute("max", "1");
  });

  it("단일 timeframe과 데이터 계약값은 숨기고 자동 설정 요약에 표시한다", async () => {
    renderManagement();

    expect(await screen.findByText("새 백테스트 설정")).toBeInTheDocument();
    expect(screen.queryByLabelText("실행 이름")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("타임프레임")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("거래소")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("마켓")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("데이터 소스")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("시드")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("지표 모드")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("trigger_feed")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("fill_timing")).not.toBeInTheDocument();

    expect(screen.getByText("bt-vessel-reference-btc")).toBeInTheDocument();
    expect(screen.getByText("Binance · 선물")).toBeInTheDocument();
    expect(screen.getByText("crypto_data.ohlcv_futures")).toBeInTheDocument();
    expect(screen.getByText("전략 자동 지표 · 다음 봉 체결")).toBeInTheDocument();
  });

  it("전략이 여러 timeframe을 지원할 때만 선택기를 노출한다", async () => {
    const user = userEvent.setup();
    server.use(...managementHandlers(["15m", "1h"]));
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );

    const timeframe = await screen.findByLabelText("타임프레임");
    expect(timeframe).toHaveValue("1h");
    await user.selectOptions(timeframe, "15m");
    expect(timeframe).toHaveValue("15m");
  });

  it("심볼 형식에서 현물 데이터셋과 마켓을 자동 해석한다", async () => {
    const user = userEvent.setup();
    renderManagement();

    const symbol = await screen.findByLabelText("심볼");
    await user.clear(symbol);
    await user.type(symbol, "ETH/USDT");

    expect(await screen.findByText("Binance · 현물")).toBeInTheDocument();
    expect(screen.getByText("crypto_data.ohlcv")).toBeInTheDocument();
  });

  it("숨긴 값과 간단 파라미터를 완전한 RunConfig로 자동 제출한다", async () => {
    const user = userEvent.setup();
    let submitted: unknown;
    server.use(
      ...managementHandlers(),
      http.post("http://localhost/api/v1/runs", async ({ request }) => {
        submitted = await request.json();
        return HttpResponse.json({
          job_id: "job-automatic-config",
          status: "QUEUED",
          events_url: "/api/v1/runs/jobs/job-automatic-config/events",
          status_url: "/api/v1/runs/jobs/job-automatic-config",
        });
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );

    expect(
      await screen.findByText(
        "이 전략에는 사용자가 조정할 기본 파라미터가 없습니다.",
      ),
    ).toBeInTheDocument();
    const rewardRisk = await screen.findByLabelText("수동 reward_risk");
    expect(rewardRisk).toHaveValue(2);
    await user.clear(rewardRisk);
    await user.type(rewardRisk, "2.5");
    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));

    await waitFor(() => expect(submitted).toBeDefined());
    expect(submitted).toMatchObject({
      config: {
        run_name: "bt-vessel-reference-btc",
        strategy_id: "vessel-reference",
        params: {},
        money_management: {
          mode: "manual",
          leverage: 1,
          reward_risk: 2.5,
          atr_stop_multiple: 1.5,
        },
        symbol: "BTC/USDT:USDT",
        exchange: "binance",
        timeframe: "1h",
        market_type: "futures",
        data_source: "crypto_data.ohlcv_futures",
        seed: 0,
        indicator_mode: "auto",
        explicit_indicators: [],
        trigger_feed: "tf_candle",
        fill_timing: "next_bar",
        profile_ref: "vessel-reference-v1",
      },
    });
  });

  it("Turtle 자동 관리에서는 수동값을 숨기고 일봉 N 정책만 제출한다", async () => {
    const user = userEvent.setup();
    let submitted: unknown;
    server.use(
      ...managementHandlers(),
      http.post("http://localhost/api/v1/runs", async ({ request }) => {
        submitted = await request.json();
        return HttpResponse.json({
          job_id: "job-turtle-config",
          status: "QUEUED",
          events_url: "/api/v1/runs/jobs/job-turtle-config/events",
          status_url: "/api/v1/runs/jobs/job-turtle-config",
        });
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );

    const mode = await screen.findByLabelText("자금 관리 방법");
    await user.selectOptions(mode, "turtle");
    expect(screen.queryByLabelText("수동 레버리지")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("수동 reward_risk")).not.toBeInTheDocument();
    expect(
      screen.getByText(/확정 일봉 N으로 거래당 위험 1% 이내 자동 계산/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
    await waitFor(() => expect(submitted).toBeDefined());
    expect(submitted).toMatchObject({
      config: {
        params: {},
        sizing_method: "risk_based",
        risk_per_trade: 0.01,
        money_management: {
          mode: "turtle",
          n_period: 20,
          n_timeframe: "1d",
          stop_n_multiple: 2,
          leverage_cap: 10,
        },
      },
    });
  });

  it("파일로 배포된 정책을 고르고 그 정책의 설정 그대로 제출한다", async () => {
    const user = userEvent.setup();
    let submitted: unknown;
    server.use(
      ...managementHandlers(["1h"], {
        supported: ["manual", "atr-only"],
        default: { mode: "atr-only", atr_stop_multiple: 3 },
      }),
      http.post("http://localhost/api/v1/runs", async ({ request }) => {
        submitted = await request.json();
        return HttpResponse.json({
          job_id: "job-deployed-policy",
          status: "QUEUED",
          events_url: "/api/v1/runs/jobs/job-deployed-policy/events",
          status_url: "/api/v1/runs/jobs/job-deployed-policy",
        });
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );

    const mode = await screen.findByLabelText("자금 관리 방법");
    expect(
      within(mode).getByRole("option", { name: "atr-only" }),
    ).toBeInTheDocument();
    await user.selectOptions(mode, "atr-only");
    await waitFor(() =>
      expect(screen.getByLabelText("배포 정책 설정")).toHaveValue(
        JSON.stringify({ atr_stop_multiple: 3 }, null, 2),
      ),
    );

    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
    await waitFor(() => expect(submitted).toBeDefined());
    expect(submitted).toMatchObject({
      config: {
        money_management: { mode: "atr-only", atr_stop_multiple: 3 },
      },
    });
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

describe("스윕 축 값", () => {
  it("축 파라미터가 정수 항목이면 값도 정수로 시작한다", async () => {
    const user = userEvent.setup();
    renderManagement();

    await user.click(await screen.findByText("스윕 설정"));
    // vessel-reference의 기본 파라미터는 모두 자금 관리 소관이라 첫 축은
    // money_management.leverage가 된다. 이 축의 기본값이 소수였던 것이 스윕
    // 실행을 실패시켰다.
    expect(screen.getByLabelText("축 1 파라미터")).toHaveValue(
      "money_management.leverage",
    );
    expect(screen.getByLabelText("축 1 값 JSON 배열")).toHaveValue("[1, 2, 3]");
    expect(screen.getByText("JSON 배열 · 값 2–20개 · 자연수 1–100")).toBeInTheDocument();

    // 두 번째 축은 기본으로 켜져 있으므로 기본 화면이 곧 2축 스윕이다.
    expect(screen.getByLabelText(/두 번째 히트맵 축/)).toBeChecked();
    expect(screen.getByLabelText("축 2 파라미터")).toHaveValue(
      "money_management.reward_risk",
    );
    expect(screen.getByLabelText("축 2 값 JSON 배열")).toHaveValue("[1.5, 2, 2.5]");
  });

  it("기본 화면 그대로 두 축을 실행하면 스키마가 받는 값이 전송된다", async () => {
    const user = userEvent.setup();
    let body: { axes: { parameter: string; values: unknown[] }[] } | null = null;
    server.use(
      http.post("http://localhost/api/v1/sweeps", async ({ request }) => {
        body = (await request.json()) as typeof body;
        return HttpResponse.json({ job_id: "job", sweep_id: "sweep" });
      }),
    );
    renderManagement();

    await user.click(await screen.findByText("스윕 설정"));
    await user.click(screen.getByLabelText(/스윕으로 실행/));
    await user.click(screen.getByRole("button", { name: "스윕 실행" }));

    await waitFor(() => expect(body).not.toBeNull());
    const axes = body!.axes;
    expect(axes[0]).toEqual({
      parameter: "money_management.leverage",
      values: [1, 2, 3],
    });
    expect(axes[0].values.every((value) => Number.isInteger(value))).toBe(true);
    expect(axes[1].parameter).toBe("money_management.reward_risk");
  });

  it("정수 축에 소수를 직접 넣으면 보내기 전에 이유를 말한다", async () => {
    const user = userEvent.setup();
    const sweepPost = vi.fn();
    server.use(
      http.post("http://localhost/api/v1/sweeps", () => {
        sweepPost();
        return HttpResponse.json({ job_id: "job", sweep_id: "sweep" });
      }),
    );
    renderManagement();

    await user.click(await screen.findByText("스윕 설정"));
    await user.click(screen.getByLabelText(/스윕으로 실행/));
    const values = screen.getByLabelText("축 1 값 JSON 배열");
    await user.clear(values);
    // "[" starts user-event keyboard syntax, so the opening bracket is escaped.
    await user.type(values, "[[1.5, 2, 2.5]");
    await user.click(screen.getByRole("button", { name: "스윕 실행" }));

    expect(
      await screen.findByText(
        "첫 번째 축의 money_management.leverage 값은 자연수만 가능합니다 (1–100).",
      ),
    ).toBeInTheDocument();
    expect(sweepPost).not.toHaveBeenCalled();
  });
});

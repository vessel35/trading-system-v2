import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import type { TrackedJob, TrackedSweep } from "../contexts/run-jobs";
import type { RunSubmission, StrategyOption } from "../api/client";
import { RunJobsProvider } from "../contexts/run-jobs";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import {
  JobRow,
  RunManagementPage,
  restoredMoneyManagementMode,
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
  profileId = "vessel-reference-v1",
) {
  return [
    http.get("http://localhost/api/v1/strategies", () =>
      HttpResponse.json({
        data: [
          {
            strategy_id: "vessel-reference",
            display_name: "Vessel",
            strategy_version: "1",
            profile_id: profileId,
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
            runnable: true,
            unrunnable_reason: null,
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

async function chooseStrategy(strategyId = "vessel-reference") {
  const selector = await screen.findByLabelText("전략");
  await waitFor(() => {
    const option = Array.from((selector as HTMLSelectElement).options).find(
      (item) => item.value === strategyId,
    );
    expect(option).toBeEnabled();
  });
  fireEvent.change(selector, { target: { value: strategyId } });
  await waitFor(() => expect(selector).toHaveValue(strategyId));
}

async function renderManagement() {
  server.use(...managementHandlers());
  const rendered = renderWithQuery(
    <RunJobsProvider>
      <RunManagementPage />
    </RunJobsProvider>,
  );
  await chooseStrategy();
  return rendered;
}

function strategyOption(
  strategyId: string,
  moneyManagement: {
    supported: string[];
    default: Record<string, unknown>;
  },
): StrategyOption {
  return {
    strategy_id: strategyId,
    display_name: strategyId,
    strategy_version: "1",
    profile_id: `${strategyId}-v1`,
    profile: {
      id: `${strategyId}-v1`,
      family: "trend",
      bar: "1h",
      expected_win_rate: [0.25, 0.65],
      expected_payoff: [1.0, 4.0],
      tail_shape: "right_fat",
      holding_horizon: "multi_day",
      primary_metric: "calmar",
      risk_adjusted_pref: "sortino",
      profit_structure_to_preserve: "fixed-risk-trend-capture",
      envelope_tolerance: 0.2,
      envelope_status: "provisional",
    },
    supported_timeframes: ["1h"],
    required_indicators: [],
    min_history: 10,
    default_params: {},
    supported_money_management: moneyManagement.supported,
    default_money_management: moneyManagement.default,
    is_active: true,
    is_deprecated: false,
    runnable: true,
    unrunnable_reason: null,
    source: "strategy_registry",
  };
}

function renderManagementPage() {
  return renderWithQuery(
    <RunJobsProvider>
      <RunManagementPage />
    </RunJobsProvider>,
  );
}

function installExecutionSpies() {
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
  return { runPost, sweepPost };
}

async function expectEveryBlockedSubmissionPath(
  runPost: ReturnType<typeof vi.fn>,
  sweepPost: ReturnType<typeof vi.fn>,
) {
  const button = await screen.findByRole("button", { name: "실행할 수 없음" });
  expect(button).toBeDisabled();
  const form = button.closest("form");
  expect(form).not.toBeNull();

  // A disabled button and a direct form submit are distinct paths. Both must
  // leave both endpoints untouched while this is a single-run submission.
  fireEvent.click(button);
  fireEvent.submit(form!);
  expect(runPost).not.toHaveBeenCalled();
  expect(sweepPost).not.toHaveBeenCalled();

  fireEvent.click(screen.getByLabelText(/스윕으로 실행/));
  const sweepButton = await screen.findByRole("button", {
    name: "실행할 수 없음",
  });
  fireEvent.click(sweepButton);
  fireEvent.submit(form!);
  expect(runPost).not.toHaveBeenCalled();
  expect(sweepPost).not.toHaveBeenCalled();
}

class RunEventSourceMock {
  static instances: RunEventSourceMock[] = [];
  private statusListener?: (event: MessageEvent<string>) => void;
  onerror: ((event: Event) => void) | null = null;

  constructor(_url: string | URL) {
    RunEventSourceMock.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    if (type === "status") {
      this.statusListener = listener as (event: MessageEvent<string>) => void;
    }
  }

  close() {}

  emitStatus(status: Record<string, unknown>) {
    this.statusListener?.(
      new MessageEvent("status", { data: JSON.stringify(status) }),
    );
  }
}

describe("실행 관리 보강", () => {
  it("연구 가설 도움말에서 사전등록 개념과 필드를 확인하고 Esc로 닫는다", async () => {
    const user = userEvent.setup();
    await renderManagement();

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
    await renderManagement();

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
    await renderManagement();

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
    await chooseStrategy();

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
    await renderManagement();

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
    await renderManagement();

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
    await renderManagement();

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
    await chooseStrategy();

    const timeframe = await screen.findByLabelText("타임프레임");
    expect(timeframe).toHaveValue("1h");
    await user.selectOptions(timeframe, "15m");
    expect(timeframe).toHaveValue("15m");
  });

  it("심볼 형식에서 현물 데이터셋과 마켓을 자동 해석한다", async () => {
    const user = userEvent.setup();
    await renderManagement();

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
    await chooseStrategy();

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

  it("전략 id 규칙과 다른 선언 profile id를 단일 실행과 스윕에 그대로 제출한다", async () => {
    const user = userEvent.setup();
    const bodies: { run?: unknown; sweep?: unknown } = {};
    server.use(
      ...managementHandlers(
        ["1h"],
        {
          supported: ["manual"],
          default: {
            mode: "manual",
            leverage: 1,
            reward_risk: 2,
            atr_stop_multiple: 1.5,
          },
        },
        "declaration-owned-profile",
      ),
      http.post("http://localhost/api/v1/runs", async ({ request }) => {
        bodies.run = await request.json();
        return HttpResponse.json({}, { status: 500 });
      }),
      http.post("http://localhost/api/v1/sweeps", async ({ request }) => {
        bodies.sweep = await request.json();
        return HttpResponse.json({}, { status: 500 });
      }),
    );
    renderManagementPage();
    await chooseStrategy();

    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
    await waitFor(() => expect(bodies.run).toBeDefined());
    expect(bodies.run).toHaveProperty(
      "config.profile_ref",
      "declaration-owned-profile",
    );

    await user.click(screen.getByLabelText(/스윕으로 실행/));
    await user.click(screen.getByRole("button", { name: "스윕 실행" }));
    await waitFor(() => expect(bodies.sweep).toBeDefined());
    expect(bodies.sweep).toHaveProperty(
      "config.profile_ref",
      "declaration-owned-profile",
    );
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
    await chooseStrategy();

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
    await chooseStrategy();

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

  it("전략이 배포 정책을 기본으로 선언하면 그 정책으로 열린다", async () => {
    server.use(
      ...managementHandlers(["1h"], {
        supported: ["manual", "atr-only"],
        default: { mode: "atr-only", atr_stop_multiple: 3 },
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();

    const mode = await screen.findByLabelText("자금 관리 방법");
    await waitFor(() => expect(mode).toHaveValue("atr-only"));
    expect(screen.getByLabelText("배포 정책 설정")).toHaveValue(
      JSON.stringify({ atr_stop_multiple: 3 }, null, 2),
    );
  });

  it("mode를 오갔다 돌아와도 배포 정책에 적은 설정이 남는다", async () => {
    const user = userEvent.setup();
    server.use(
      ...managementHandlers(["1h"], {
        supported: ["manual", "atr-only"],
        default: { mode: "atr-only", atr_stop_multiple: 3 },
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();

    const mode = await screen.findByLabelText("자금 관리 방법");
    await waitFor(() => expect(mode).toHaveValue("atr-only"));
    const box = screen.getByLabelText("배포 정책 설정");
    await user.clear(box);
    await user.type(box, '{{"atr_stop_multiple": 9}');

    await user.selectOptions(mode, "manual");
    await user.selectOptions(mode, "atr-only");

    expect(screen.getByLabelText("배포 정책 설정")).toHaveValue(
      '{"atr_stop_multiple": 9}',
    );
  });

  it("같은 전략 목록을 다시 받아도 사용자가 고른 mode와 설정을 보존한다", async () => {
    const user = userEvent.setup();
    let fetches = 0;
    server.use(
      http.get("http://localhost/api/v1/strategies", () => {
        fetches += 1;
        return HttpResponse.json({
          data: [
            {
              ...strategyOption("vessel-reference", {
                supported: ["manual", "atr-only"],
                default: { mode: "atr-only", atr_stop_multiple: 3 },
              }),
              // A catalog refresh may change presentation metadata without
              // changing the strategy contract the form is editing.
              display_name: `Vessel ${fetches}`,
            },
          ],
        });
      }),
      ...managementHandlers().slice(1),
    );
    const { queryClient } = renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();

    const mode = await screen.findByLabelText("자금 관리 방법");
    await waitFor(() => expect(mode).toHaveValue("atr-only"));
    const box = screen.getByLabelText("배포 정책 설정");
    await user.clear(box);
    await user.type(box, '{{"atr_stop_multiple": 9}');

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });

    await waitFor(() => expect(fetches).toBe(2));
    await waitFor(() => expect(mode).toHaveValue("atr-only"));
    expect(screen.getByLabelText("배포 정책 설정")).toHaveValue(
      '{"atr_stop_multiple": 9}',
    );
  });

  it("전략 A→B는 B 기본값을 쓰고 B→A는 앞서 편집한 A 값을 복원한다", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            strategyOption("vessel-reference", {
              supported: ["manual", "turtle"],
              default: { mode: "manual", leverage: 1 },
            }),
            strategyOption("breakout", {
              supported: ["manual", "turtle"],
              default: { mode: "turtle", n_period: 20 },
            }),
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();

    const strategy = await screen.findByLabelText("전략");
    const leverage = await screen.findByLabelText("수동 레버리지");
    await user.clear(leverage);
    await user.type(leverage, "7");

    await user.selectOptions(strategy, "breakout");
    await waitFor(() =>
      expect(screen.getByLabelText("자금 관리 방법")).toHaveValue("turtle"),
    );

    await user.selectOptions(strategy, "vessel-reference");
    await waitFor(() =>
      expect(screen.getByLabelText("자금 관리 방법")).toHaveValue("manual"),
    );
    expect(screen.getByLabelText("수동 레버리지")).toHaveValue(7);
  });

  it("다른 전략의 실패한 제출을 불러오면 복원값을 기본값으로 덮지 않는다", async () => {
    const user = userEvent.setup();
    const originalEventSource = globalThis.EventSource;
    RunEventSourceMock.instances = [];
    Object.defineProperty(globalThis, "EventSource", {
      configurable: true,
      value: RunEventSourceMock,
    });
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            strategyOption("vessel-reference", {
              supported: ["manual", "turtle"],
              default: { mode: "manual", leverage: 1 },
            }),
            strategyOption("breakout", {
              supported: ["manual", "turtle"],
              default: { mode: "turtle", n_period: 20 },
            }),
          ],
        }),
      ),
      ...managementHandlers().slice(1),
      http.post("http://localhost/api/v1/runs", () =>
        HttpResponse.json({
          job_id: "failed-a",
          status: "QUEUED",
          events_url: "/events/failed-a",
          status_url: "/status/failed-a",
        }),
      ),
    );
    try {
      renderWithQuery(
        <RunJobsProvider>
          <RunManagementPage />
        </RunJobsProvider>,
      );
      await chooseStrategy();
      const strategy = await screen.findByLabelText("전략");
      const leverage = await screen.findByLabelText("수동 레버리지");
      await user.clear(leverage);
      await user.type(leverage, "7");
      await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
      await waitFor(() => expect(RunEventSourceMock.instances).toHaveLength(1));
      act(() => {
        RunEventSourceMock.instances[0].emitStatus({
          job_id: "failed-a",
          status: "FAILED",
          updated_at: "2026-01-01T00:00:00Z",
        });
      });

      await user.selectOptions(strategy, "breakout");
      await user.click(await screen.findByRole("button", { name: "폼 수정" }));

      await waitFor(() => expect(strategy).toHaveValue("vessel-reference"));
      expect(screen.getByLabelText("자금 관리 방법")).toHaveValue("manual");
      expect(screen.getByLabelText("수동 레버리지")).toHaveValue(7);
    } finally {
      Object.defineProperty(globalThis, "EventSource", {
        configurable: true,
        value: originalEventSource,
      });
      RunEventSourceMock.instances = [];
    }
  });

  it("같은 전략의 새 계약이 현재 선택을 제외하면 알리고 제출을 막는다", async () => {
    const user = userEvent.setup();
    let supported = ["manual", "turtle"];
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            strategyOption("vessel-reference", {
              supported,
              default: { mode: "manual", leverage: 1 },
            }),
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { queryClient } = renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();
    const mode = await screen.findByLabelText("자금 관리 방법");
    await user.selectOptions(mode, "turtle");
    supported = ["manual"];

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });

    expect(
      await screen.findByText(/자금 관리 turtle 정책을 더는 지원하지 않습니다/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "실행할 수 없음" })).toBeDisabled();
  });

  it("설정 JSON의 mode는 고른 정책을 덮지 못한다", async () => {
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
          job_id: "job-mode-key",
          status: "QUEUED",
          events_url: "/api/v1/runs/jobs/job-mode-key/events",
          status_url: "/api/v1/runs/jobs/job-mode-key",
        });
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();

    const mode = await screen.findByLabelText("자금 관리 방법");
    await waitFor(() => expect(mode).toHaveValue("atr-only"));
    const box = screen.getByLabelText("배포 정책 설정");
    await user.clear(box);
    await user.type(box, '{{"mode": "manual"}');

    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
    await waitFor(() => expect(submitted).toBeDefined());
    expect(submitted).toMatchObject({
      config: { money_management: { mode: "atr-only" } },
    });
  });

  it("설정을 비우면 정책 기본값으로 제출한다", async () => {
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
          job_id: "job-empty-json",
          status: "QUEUED",
          events_url: "/api/v1/runs/jobs/job-empty-json/events",
          status_url: "/api/v1/runs/jobs/job-empty-json",
        });
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();

    const mode = await screen.findByLabelText("자금 관리 방법");
    await waitFor(() => expect(mode).toHaveValue("atr-only"));
    await user.clear(screen.getByLabelText("배포 정책 설정"));

    await user.click(screen.getByRole("button", { name: "백테스트 실행" }));
    await waitFor(() => expect(submitted).toBeDefined());
    expect(submitted).toMatchObject({
      config: { money_management: { mode: "atr-only" } },
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
    await renderManagement();

    expect(await screen.findByLabelText("스윕 ID")).toHaveValue("past-sweep");
    expect(screen.getByLabelText("열린 스윕")).toHaveTextContent("past-sweep");
  });

  it("사전등록 잠금 기능을 쓰기 엔드포인트 미구현 3차 유보로 명시한다", async () => {
    await renderManagement();

    expect(
      await screen.findByText(/사전등록 잠금은 쓰기 엔드포인트 미구현으로 유보\(3차\)/),
    ).toBeInTheDocument();
  });
});

describe("실행 가능 판정", () => {
  it("전략 목록을 아직 받지 못한 상태를 모든 제출 경로에서 막는다", async () => {
    server.use(
      http.get(
        "http://localhost/api/v1/strategies",
        async () => await new Promise<never>(() => {}),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    renderManagementPage();

    expect(
      await screen.findByText("전략 목록을 아직 받지 못했습니다."),
    ).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("전략 목록 첫 조회 실패를 모든 제출 경로에서 막는다", async () => {
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({ detail: "failed" }, { status: 500 }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    renderManagementPage();

    expect(
      await screen.findByText("전략 목록을 처음 조회하지 못했습니다. 다시 조회하세요."),
    ).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("이전 목록을 가진 재조회 실패를 첫 조회 실패와 구분해 모든 제출 경로에서 막는다", async () => {
    let fetches = 0;
    server.use(
      http.get("http://localhost/api/v1/strategies", () => {
        fetches += 1;
        return fetches === 1
          ? HttpResponse.json({
              data: [
                strategyOption("vessel-reference", {
                  supported: ["manual"],
                  default: { mode: "manual" },
                }),
              ],
            })
          : HttpResponse.json({ detail: "failed" }, { status: 500 });
      }),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    const { queryClient } = renderManagementPage();
    await chooseStrategy();

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });
    expect(
      await screen.findByText(/이전 전략 목록은 남아 있지만 최신 목록을 다시 받지 못했습니다/),
    ).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("빈 전략 목록을 모든 제출 경로에서 막는다", async () => {
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({ data: [] }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    renderManagementPage();

    expect(await screen.findByText("실행할 전략이 없습니다.")).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("사람이 아직 전략을 고르지 않은 상태를 모든 제출 경로에서 막는다", async () => {
    server.use(...managementHandlers());
    const { runPost, sweepPost } = installExecutionSpies();
    renderManagementPage();

    expect(await screen.findByText("실행할 전략을 선택하세요.")).toBeInTheDocument();
    expect(screen.getByLabelText("전략")).toHaveValue("");
    expect(screen.queryByText("직접 설정")).not.toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("고른 전략이 최신 응답에서 사라진 상태를 모든 제출 경로에서 막는다", async () => {
    let strategies = [
      strategyOption("vessel-reference", {
        supported: ["manual"],
        default: { mode: "manual" },
      }),
    ];
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({ data: strategies }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    const { queryClient } = renderManagementPage();
    await chooseStrategy();
    strategies = [
      strategyOption("breakout", {
        supported: ["manual"],
        default: { mode: "manual" },
      }),
    ];

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });
    expect(
      await screen.findByText(/vessel-reference이 최신 전략 목록에 없습니다/),
    ).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("서버가 고른 전략을 실행 불가로 바꾼 상태를 모든 제출 경로에서 막는다", async () => {
    let runnable = true;
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            {
              ...strategyOption("vessel-reference", {
                supported: ["manual"],
                default: { mode: "manual" },
              }),
              runnable,
              unrunnable_reason: runnable ? null : "inactive",
            },
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    const { queryClient } = renderManagementPage();
    await chooseStrategy();
    runnable = false;

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });
    expect(
      await screen.findAllByText(/등록 정보에서 비활성화된 전략입니다/),
    ).not.toHaveLength(0);
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("고른 전략의 profile_id가 null이면 버튼과 폼 제출의 단일·스윕 네 경로를 막는다", async () => {
    let profileId: string | null = "declaration-owned-profile";
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            {
              ...strategyOption("vessel-reference", {
                supported: ["manual"],
                default: { mode: "manual" },
              }),
              profile_id: profileId,
            },
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    const { queryClient } = renderManagementPage();
    await chooseStrategy();
    profileId = null;

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });
    expect(
      await screen.findByText(/선언한 성격 정보 id를 읽을 수 없어 실행할 수 없습니다/),
    ).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("고른 timeframe이 새 지원 목록에 없는 상태를 모든 제출 경로에서 막는다", async () => {
    let supportedTimeframes = ["1h", "15m"];
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            {
              ...strategyOption("vessel-reference", {
                supported: ["manual"],
                default: { mode: "manual" },
              }),
              supported_timeframes: supportedTimeframes,
            },
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    const { queryClient } = renderManagementPage();
    await chooseStrategy();
    fireEvent.change(screen.getByLabelText("타임프레임"), {
      target: { value: "15m" },
    });
    supportedTimeframes = ["1h"];

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });
    expect(
      await screen.findByText(/timeframe 15m을 지원하지 않습니다/),
    ).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("고른 정책이 새 지원 목록에 없는 상태를 모든 제출 경로에서 막는다", async () => {
    let supportedModes = ["manual", "turtle"];
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            strategyOption("vessel-reference", {
              supported: supportedModes,
              default: { mode: "manual" },
            }),
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    const { queryClient } = renderManagementPage();
    await chooseStrategy();
    fireEvent.change(screen.getByLabelText("자금 관리 방법"), {
      target: { value: "turtle" },
    });
    supportedModes = ["manual"];

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });
    expect(
      await screen.findByText(/자금 관리 turtle 정책을 더는 지원하지 않습니다/),
    ).toBeInTheDocument();
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("기본 정책이 빠져 사람이 아직 정책을 고르지 않은 상태를 모든 제출 경로에서 막는다", async () => {
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            strategyOption("vessel-reference", {
              supported: ["manual", "turtle"],
              default: {},
            }),
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    renderManagementPage();
    await chooseStrategy();

    expect(
      await screen.findByText(/기본 자금 관리 정책이 없어 아직 정책을 고르지 않았습니다/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("자금 관리 방법")).toHaveValue("");
    await expectEveryBlockedSubmissionPath(runPost, sweepPost);
  });

  it("전략 변경과 같은 이벤트 턴의 버튼·폼 제출에서 이전 설정을 단일·스윕으로 보내지 않는다", async () => {
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            strategyOption("vessel-reference", {
              supported: ["manual"],
              default: { mode: "manual", leverage: 1 },
            }),
            strategyOption("breakout", {
              supported: ["manual"],
              default: { mode: "manual", leverage: 9 },
            }),
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { runPost, sweepPost } = installExecutionSpies();
    renderManagementPage();
    await chooseStrategy();
    const strategy = screen.getByLabelText("전략") as HTMLSelectElement;
    const button = screen.getByRole("button", { name: "백테스트 실행" });
    const form = button.closest("form")!;

    act(() => {
      strategy.value = "breakout";
      strategy.dispatchEvent(new Event("change", { bubbles: true }));
      button.click();
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    expect(runPost).not.toHaveBeenCalled();
    expect(sweepPost).not.toHaveBeenCalled();

    await waitFor(() => expect(strategy).toHaveValue("breakout"));
    fireEvent.click(screen.getByLabelText(/스윕으로 실행/));
    const sweepButton = screen.getByRole("button", { name: "스윕 실행" });
    act(() => {
      strategy.value = "vessel-reference";
      strategy.dispatchEvent(new Event("change", { bubbles: true }));
      sweepButton.click();
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    expect(runPost).not.toHaveBeenCalled();
    expect(sweepPost).not.toHaveBeenCalled();
  });

  it.each([
    ["catalog_only", "등록 정보는 있지만 배포된 코드가 없습니다."],
    ["allowlist_only", "배포된 코드는 있지만 등록 정보가 없습니다."],
    ["identity_mismatch", "등록 정보와 배포 코드의 신원이 일치하지 않습니다."],
    ["inactive", "등록 정보에서 비활성화된 전략입니다."],
    ["deprecated", "폐기된 전략입니다."],
    ["declaration_mismatch", "등록 정보와 배포 코드의 실행 선언이 일치하지 않습니다."],
    ["declaration_read_failed", "배포 코드의 실행 선언을 읽지 못했습니다."],
  ] as const)("서버 사유 %s를 사람이 읽을 수 있는 말로 그대로 보인다", async (reason, label) => {
    let runnable = true;
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            {
              ...strategyOption("vessel-reference", {
                supported: ["manual"],
                default: { mode: "manual" },
              }),
              runnable,
              unrunnable_reason: runnable ? null : reason,
            },
          ],
        }),
      ),
      ...managementHandlers().slice(1),
    );
    const { queryClient } = renderManagementPage();
    await chooseStrategy();
    runnable = false;

    await queryClient.invalidateQueries({ queryKey: ["strategies"] });
    expect(await screen.findAllByText(new RegExp(label))).not.toHaveLength(0);
    expect(
      within(screen.getByLabelText("전략")).getByRole("option", {
        name: new RegExp(label),
      }),
    ).toBeDisabled();
  });

  it("정책 목록이 빈 전략은 단일·스윕 payload에서 자금 관리를 생략한다", async () => {
    const bodies: { run?: Record<string, unknown>; sweep?: Record<string, unknown> } = {};
    server.use(
      http.get("http://localhost/api/v1/strategies", () =>
        HttpResponse.json({
          data: [
            strategyOption("vessel-reference", { supported: [], default: {} }),
          ],
        }),
      ),
      ...managementHandlers().slice(1),
      http.post("http://localhost/api/v1/runs", async ({ request }) => {
        bodies.run = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({}, { status: 500 });
      }),
      http.post("http://localhost/api/v1/sweeps", async ({ request }) => {
        bodies.sweep = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({}, { status: 500 });
      }),
    );
    renderManagementPage();
    await chooseStrategy();

    expect(screen.queryByLabelText("자금 관리 방법")).not.toBeInTheDocument();
    expect(screen.getByText(/자금 관리 정책을 사용하지 않습니다/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "백테스트 실행" }));
    await waitFor(() => expect(bodies.run).toBeDefined());
    expect(bodies.run).not.toHaveProperty("config.money_management");

    fireEvent.click(screen.getByLabelText(/스윕으로 실행/));
    fireEvent.change(screen.getByLabelText("유형"), {
      target: { value: "walk_forward" },
    });
    fireEvent.click(screen.getByRole("button", { name: "스윕 실행" }));
    await waitFor(() => expect(bodies.sweep).toBeDefined());
    expect(bodies.sweep).not.toHaveProperty("config.money_management");
  });

  it("실패한 실행 설정에 자금 관리가 없어도 manual을 만들어 복원하지 않는다", () => {
    const submission = {
      config: {
        run_name: "no-policy",
        strategy_id: "vessel-reference",
      },
    } as RunSubmission;

    expect(restoredMoneyManagementMode(submission)).toBe("");
  });
});

describe("스윕 축 값", () => {
  it("축 후보 없는 grid만 막고 walk-forward와 IS/OOS는 제출한다", async () => {
    const user = userEvent.setup();
    const submissions: Record<string, unknown>[] = [];
    server.use(
      ...managementHandlers(["1h"], {
        supported: ["atr-only"],
        default: { mode: "atr-only", atr_stop_multiple: 3 },
      }),
      http.post("http://localhost/api/v1/sweeps", async ({ request }) => {
        submissions.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json({ job_id: `job-${submissions.length}`, sweep_id: "sweep" });
      }),
    );
    renderWithQuery(
      <RunJobsProvider>
        <RunManagementPage />
      </RunJobsProvider>,
    );
    await chooseStrategy();

    await user.click(await screen.findByText("스윕 설정"));
    await user.click(screen.getByLabelText(/스윕으로 실행/));
    const gridButton = await screen.findByRole("button", {
      name: "grid 축을 입력하세요",
    });
    expect(gridButton).toBeDisabled();
    expect(screen.getByText("스윕 설정").textContent).toMatch(/유효한 축 필요/);
    expect(screen.getByLabelText("축 1 파라미터")).toHaveValue("");

    await user.selectOptions(screen.getByLabelText("유형"), "walk_forward");
    await user.click(screen.getByRole("button", { name: "스윕 실행" }));
    await waitFor(() => expect(submissions).toHaveLength(1));
    expect(submissions[0]).toMatchObject({ type: "walk_forward", folds: 3 });
    expect(submissions[0]).not.toHaveProperty("axes");

    await user.selectOptions(screen.getByLabelText("유형"), "is_oos");
    await user.click(screen.getByRole("button", { name: "스윕 실행" }));
    await waitFor(() => expect(submissions).toHaveLength(2));
    expect(submissions[1]).toMatchObject({ type: "is_oos" });
    expect(submissions[1]).not.toHaveProperty("axes");
  });

  it("축 파라미터가 정수 항목이면 값도 정수로 시작한다", async () => {
    const user = userEvent.setup();
    await renderManagement();

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
    await renderManagement();

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
    await renderManagement();

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

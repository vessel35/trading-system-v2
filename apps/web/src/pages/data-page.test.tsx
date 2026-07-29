import {
  act,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import type { DataJobStatus } from "../api/client";
import { renderWithQuery } from "../test/render";
import {
  inventoryFixture,
  inventoryHandlers,
} from "../test/fixtures/inventory";
import { server } from "../test/server";
import { DataPage } from "./data-page";

const endpoint =
  "http://localhost/api/v1/data-sources/crypto_data.ohlcv_futures/inventory";
const dataJobsEndpoint = "http://localhost/api/v1/data-jobs";
const originalEventSource = globalThis.EventSource;

function dataJob(
  status: DataJobStatus["status"],
  overrides: Partial<DataJobStatus> = {},
): DataJobStatus {
  return {
    job_id: "data-job-1",
    operation: "backfill",
    symbol: "BTC/USDT:USDT",
    exchange: "binance",
    start: "2026-01-01T00:00:00Z",
    end: "2026-01-02T00:00:00Z",
    status,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

class MockEventSource {
  static instances: MockEventSource[] = [];

  readonly url: string;
  onerror: ((event: Event) => void) | null = null;
  private readonly listeners = new Map<string, EventListener[]>();

  constructor(url: string | URL) {
    this.url = url.toString();
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    const current = this.listeners.get(type) ?? [];
    this.listeners.set(type, [...current, listener]);
  }

  close() {}

  emitStatus(status: DataJobStatus) {
    const event = new MessageEvent("status", {
      data: JSON.stringify(status),
    });
    this.listeners.get("status")?.forEach((listener) => listener(event));
  }
}

function installEventSourceMock() {
  MockEventSource.instances = [];
  Object.defineProperty(globalThis, "EventSource", {
    configurable: true,
    writable: true,
    value: MockEventSource,
  });
}

async function selectDateTime(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  value: string,
) {
  const trigger = screen.getByRole("button", { name: label });
  const currentMonth = /(\d{4})-(\d{2})/.exec(trigger.textContent ?? "");
  const target = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2})$/.exec(value);
  if (!currentMonth || !target) {
    throw new Error(`날짜 선택기 테스트 값을 해석할 수 없습니다: ${value}`);
  }

  await user.click(trigger);
  const dialog = screen.getByRole("dialog", { name: `${label} 선택` });
  const monthDifference =
    (Number(target[1]) - Number(currentMonth[1])) * 12 +
    Number(target[2]) -
    Number(currentMonth[2]);
  const direction = monthDifference < 0 ? "이전 달" : "다음 달";
  for (let index = 0; index < Math.abs(monthDifference); index += 1) {
    await user.click(within(dialog).getByRole("button", { name: direction }));
  }
  await user.click(
    within(dialog).getByRole("button", {
      name: `${Number(target[1])}년 ${Number(target[2])}월 ${Number(target[3])}일 선택`,
    }),
  );
  fireEvent.change(within(dialog).getByLabelText("시간"), {
    target: { value: target[4] },
  });
  await user.click(
    within(dialog).getByRole("button", { name: "선택 완료" }),
  );
}

beforeEach(() => {
  server.use(
    http.get(dataJobsEndpoint, () => HttpResponse.json([])),
  );
});

afterEach(() => {
  Object.defineProperty(globalThis, "EventSource", {
    configurable: true,
    writable: true,
    value: originalEventSource,
  });
  MockEventSource.instances = [];
});

describe("시장 데이터 인벤토리", () => {
  it("MSW 인벤토리 픽스처를 커버리지 표로 렌더한다", async () => {
    server.use(...inventoryHandlers);
    renderWithQuery(<DataPage />);

    expect(
      screen.getByText(/crypto_data는 1분봉만 저장하며 상위 타임프레임은 연속집계입니다/),
    ).toBeInTheDocument();
    const bitcoin = await screen.findByText("BTC/USDT:USDT");
    const row = bitcoin.closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("binance")).toBeInTheDocument();
    expect(within(row!).getByText("1m")).toBeInTheDocument();
    expect(within(row!).getByText("470,000")).toBeInTheDocument();
    expect(within(row!).getByText("498,241")).toBeInTheDocument();
    expect(within(row!).getByText("28,241")).toBeInTheDocument();
    expect(
      within(row!).getByRole("progressbar", { name: "BTC/USDT:USDT 커버리지" }),
    ).toHaveValue(inventoryFixture.items[0].coverage_ratio);
  });

  it("인벤토리가 비어 있으면 빈 상태를 표시한다", async () => {
    server.use(
      http.get(endpoint, () =>
        HttpResponse.json({
          data_source: "crypto_data.ohlcv_futures",
          items: [],
        }),
      ),
    );
    renderWithQuery(<DataPage />);

    expect(
      await screen.findByText("저장된 1분봉 데이터가 없습니다."),
    ).toBeInTheDocument();
  });

  it("API 오류와 다시 시도 동작을 표준 오류 상태로 표시한다", async () => {
    server.use(
      http.get(endpoint, () =>
        HttpResponse.json(
          {
            error: {
              code: "catalog_unavailable",
              message: "crypto_data 연결을 열 수 없습니다.",
              details: null,
            },
          },
          { status: 503 },
        ),
      ),
    );
    renderWithQuery(<DataPage />);

    expect(
      await screen.findByText("데이터 인벤토리를 불러오지 못했습니다."),
    ).toBeInTheDocument();
    expect(screen.getByText("crypto_data 연결을 열 수 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("데이터 수집·backfill 실행", () => {
  it("쓰기 경고와 폼을 렌더하고 refresh_aggregates에서만 기본 timeframes를 표시한다", async () => {
    const user = userEvent.setup();
    server.use(...inventoryHandlers);
    renderWithQuery(<DataPage />);

    expect(
      screen.getByText("인벤토리 조회만 읽기 전용"),
    ).toBeInTheDocument();
    const warning = screen.getByRole("alert");
    expect(
      within(warning).getByText("실제 쓰기 작업 · DRY-RUN 아님"),
    ).toBeInTheDocument();
    expect(
      within(warning).getByText(/실제 시장 데이터를 crypto_data에 씁니다/),
    ).toBeInTheDocument();
    const symbolInput = await screen.findByLabelText("심볼 (CCXT 형식)");
    expect(symbolInput).toHaveValue("BTC/USDT:USDT");
    expect(symbolInput).not.toHaveAttribute("list");
    expect(document.querySelector("datalist")).not.toBeInTheDocument();
    expect(screen.getByLabelText("거래소")).toBeDisabled();
    expect(screen.getByLabelText("작업")).toHaveValue("backfill");
    expect(
      screen.getByRole("button", { name: "시작 (UTC)" }),
    ).toHaveTextContent(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/);
    expect(
      screen.getByRole("button", { name: "종료 (UTC)" }),
    ).toHaveTextContent(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/);
    expect(screen.queryByRole("group", { name: "timeframes" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("작업"), "refresh_aggregates");
    const timeframes = screen.getByRole("group", { name: "timeframes" });
    const checkboxes = within(timeframes).getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(5);
    checkboxes.forEach((checkbox) => expect(checkbox).toBeChecked());

    await user.selectOptions(screen.getByLabelText("작업"), "funding_backfill");
    expect(screen.queryByRole("group", { name: "timeframes" })).not.toBeInTheDocument();
  });

  it("빈 심볼과 역전 기간을 제출 전에 차단하며 확인 Dialog와 POST를 만들지 않는다", async () => {
    const user = userEvent.setup();
    const post = vi.fn();
    server.use(
      ...inventoryHandlers,
      http.post(dataJobsEndpoint, () => {
        post();
        return HttpResponse.json(dataJob("QUEUED"), { status: 202 });
      }),
    );
    renderWithQuery(<DataPage />);

    const symbol = await screen.findByLabelText("심볼 (CCXT 형식)");
    await user.clear(symbol);
    await selectDateTime(user, "시작 (UTC)", "2026-01-02T00:00");
    await selectDateTime(user, "종료 (UTC)", "2026-01-01T00:00");
    await user.click(screen.getByRole("button", { name: "실행 내용 확인" }));

    expect(screen.getByText("심볼을 입력하세요.")).toBeInTheDocument();
    expect(
      screen.getByText("종료 시각은 시작 시각보다 뒤여야 합니다."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("확인 Dialog에서는 심볼·작업·기간을 되비추며 명시적 실행 전에는 POST하지 않는다", async () => {
    const user = userEvent.setup();
    const post = vi.fn();
    server.use(
      ...inventoryHandlers,
      http.post(dataJobsEndpoint, () => {
        post();
        return HttpResponse.json(dataJob("QUEUED"), { status: 202 });
      }),
    );
    renderWithQuery(<DataPage />);

    await screen.findByLabelText("심볼 (CCXT 형식)");
    await selectDateTime(user, "시작 (UTC)", "2026-01-01T00:00");
    await selectDateTime(user, "종료 (UTC)", "2026-01-02T00:00");
    await user.click(screen.getByRole("button", { name: "실행 내용 확인" }));

    const dialog = screen.getByRole("dialog", {
      name: "실제 시장 데이터 쓰기를 실행하시겠습니까?",
    });
    expect(within(dialog).getByText("BTC/USDT:USDT")).toBeInTheDocument();
    expect(
      within(dialog).getByText("backfill · OHLCV 1분봉"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/2026/)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: "취소" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("확인 후 POST하고 SSE로 QUEUED→RUNNING→SUCCEEDED 상태를 갱신한다", async () => {
    installEventSourceMock();
    const user = userEvent.setup();
    const postBodies: unknown[] = [];
    let inventoryRequests = 0;
    const queued = dataJob("QUEUED");
    server.use(
      http.get(endpoint, () => {
        inventoryRequests += 1;
        return HttpResponse.json(inventoryFixture);
      }),
      http.post(dataJobsEndpoint, async ({ request }) => {
        postBodies.push(await request.json());
        return HttpResponse.json(queued, { status: 202 });
      }),
    );
    const { queryClient } = renderWithQuery(<DataPage />);
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    await screen.findByLabelText("심볼 (CCXT 형식)");
    await selectDateTime(user, "시작 (UTC)", "2026-01-01T00:00");
    await selectDateTime(user, "종료 (UTC)", "2026-01-02T00:00");
    await user.click(screen.getByRole("button", { name: "실행 내용 확인" }));
    expect(postBodies).toHaveLength(0);
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "실행" }),
    );

    const row = await screen.findByTestId("data-job-data-job-1");
    expect(within(row).getByText("QUEUED")).toBeInTheDocument();
    expect(postBodies).toEqual([
      {
        operation: "backfill",
        symbol: "BTC/USDT:USDT",
        exchange: "binance",
        start: "2026-01-01T00:00:00.000Z",
        end: "2026-01-02T00:00:00.000Z",
      },
    ]);
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    act(() => {
      MockEventSource.instances[0].emitStatus(
        dataJob("RUNNING", { updated_at: "2026-01-01T00:01:00Z" }),
      );
    });
    expect(await within(row).findByText("RUNNING")).toBeInTheDocument();
    const progress = within(row).getByRole("progressbar", {
      name: "BTC/USDT:USDT 데이터 작업 실행 중",
    });
    expect(progress).not.toHaveAttribute("aria-valuenow");
    expect(progress).toHaveAttribute(
      "aria-valuetext",
      "서버 수치 진행률 미제공",
    );

    act(() => {
      MockEventSource.instances[0].emitStatus(
        dataJob("SUCCEEDED", { updated_at: "2026-01-01T00:02:00Z" }),
      );
    });
    expect(await within(row).findByText("SUCCEEDED")).toBeInTheDocument();
    await waitFor(() => expect(inventoryRequests).toBe(2));
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["coverage"] });
  });

  it("SSE 오류 시 개별 상태 GET으로 폴백한다", async () => {
    installEventSourceMock();
    const queued = dataJob("QUEUED");
    const succeeded = dataJob("SUCCEEDED", {
      updated_at: "2026-01-01T00:03:00Z",
    });
    server.use(
      ...inventoryHandlers,
      http.get(dataJobsEndpoint, () => HttpResponse.json([queued])),
      http.get(`${dataJobsEndpoint}/:jobId`, () => HttpResponse.json(succeeded)),
    );
    renderWithQuery(<DataPage />);

    const row = await screen.findByTestId("data-job-data-job-1");
    expect(within(row).getByText("QUEUED")).toBeInTheDocument();
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    act(() => {
      MockEventSource.instances[0].onerror?.(new Event("error"));
    });

    expect(await within(row).findByText("SUCCEEDED")).toBeInTheDocument();
  });

  it("FAILED 상태에서 서버의 안전한 오류 code와 message를 표시한다", async () => {
    server.use(
      ...inventoryHandlers,
      http.get(dataJobsEndpoint, () =>
        HttpResponse.json([
          dataJob("FAILED", {
            error: {
              code: "collector_failed",
              message: "수집기가 안전하게 종료되었습니다.",
            },
          }),
        ]),
      ),
    );
    renderWithQuery(<DataPage />);

    const row = await screen.findByTestId("data-job-data-job-1");
    expect(within(row).getByText("FAILED")).toBeInTheDocument();
    expect(within(row).getByText("collector_failed")).toBeInTheDocument();
    expect(
      within(row).getByText("수집기가 안전하게 종료되었습니다."),
    ).toBeInTheDocument();
  });

  it("이미 성공한 작업을 처음 불러올 때 인벤토리를 중복 조회하지 않는다", async () => {
    let inventoryRequests = 0;
    server.use(
      http.get(endpoint, () => {
        inventoryRequests += 1;
        return HttpResponse.json(inventoryFixture);
      }),
      http.get(dataJobsEndpoint, () =>
        HttpResponse.json([dataJob("SUCCEEDED")]),
      ),
    );
    renderWithQuery(<DataPage />);

    const row = await screen.findByTestId("data-job-data-job-1");
    expect(within(row).getByText("SUCCEEDED")).toBeInTheDocument();
    await waitFor(() => expect(inventoryRequests).toBe(1));
  });
});

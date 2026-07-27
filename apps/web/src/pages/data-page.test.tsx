import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderWithQuery } from "../test/render";
import {
  inventoryFixture,
  inventoryHandlers,
} from "../test/fixtures/inventory";
import { server } from "../test/server";
import { DataPage } from "./data-page";

const endpoint =
  "http://localhost/api/v1/data-sources/crypto_data.ohlcv_futures/inventory";

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

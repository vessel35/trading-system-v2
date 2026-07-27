import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "../error-boundary";
import {
  EVIDENCE_ROW_LIMIT,
  useSignals,
} from "../../hooks/use-evidence";
import {
  largeEvidenceHandlers,
  standardErrorHandlers,
} from "../../test/fixtures/evidence";
import { renderWithQuery } from "../../test/render";
import { server } from "../../test/server";
import { EvidenceTruncationNotice } from "./evidence-state";
import {
  EquityDrawdownTab,
  equityMarkerTime,
} from "./equity-drawdown-tab";
import { SignalsDecisionsTab } from "./signals-decisions-tab";

function ThrowingComponent(): never {
  throw new Error("fixture render failure");
}

function LargeEvidenceProbe() {
  const signals = useSignals("fixture-large");
  if (signals.isLoading) return <p>loading</p>;
  if (signals.error) throw signals.error;
  return (
    <>
      <output aria-label="로드된 Evidence 행">{signals.data?.length ?? 0}</output>
      <EvidenceTruncationNotice sources={[signals.data]} />
    </>
  );
}

describe("Evidence 경계 시나리오", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("빈 Evidence 응답에서 드로다운 사건 0건을 크래시 없이 표시한다", async () => {
    renderWithQuery(
      <EquityDrawdownTab runId="fixture-empty" onSelectTrade={vi.fn()} />,
    );

    expect(await screen.findByText("드로다운 사건이 없습니다.")).toBeInTheDocument();
  });

  it("표준 오류 응답의 code와 message를 Evidence 오류 UI에 보존한다", async () => {
    server.use(...standardErrorHandlers);
    renderWithQuery(
      <SignalsDecisionsTab runId="fixture-error" onSelectTrade={vi.fn()} />,
    );

    expect(await screen.findByText("표준 Evidence 오류 픽스처")).toBeInTheDocument();
    expect(screen.getByText("fixture_evidence_error")).toBeInTheDocument();
  });

  it("다중 커서 거대 응답을 5,000행에서 자르고 절단 고지를 표시한다", async () => {
    server.use(...largeEvidenceHandlers);
    renderWithQuery(<LargeEvidenceProbe />);

    expect(await screen.findByLabelText("로드된 Evidence 행")).toHaveTextContent(
      String(EVIDENCE_ROW_LIMIT),
    );
    const notice = screen.getByText(/Evidence 안전 상한/).closest('[role="status"]');
    expect(notice).toHaveTextContent("표시된 결과는 일부");
    expect(notice).toHaveTextContent("25페이지");
  });

  it("앱 루트 ErrorBoundary가 백지 화면 대신 복구 UI를 표시한다", () => {
    render(
      <ErrorBoundary scope="app">
        <ThrowingComponent />
      </ErrorBoundary>,
    );

    expect(
      screen.getByText("화면을 표시하는 중 문제가 발생했습니다."),
    ).toBeInTheDocument();
  });

  it("Evidence 탭 ErrorBoundary가 렌더 예외를 탭 내부에 격리한다", () => {
    render(
      <ErrorBoundary scope="evidence">
        <ThrowingComponent />
      </ErrorBoundary>,
    );

    expect(
      screen.getByText("이 Evidence 탭을 표시하지 못했습니다."),
    ).toBeInTheDocument();
  });

  it("자본곡선 매매 마커를 실제 계열의 5분 버킷 폭으로 내린다", () => {
    const start = Date.parse("2025-01-01T10:00:00Z") / 1_000;
    const data = [
      { time: start as never, value: 100 },
      { time: (start + 300) as never, value: 101 },
      { time: (start + 600) as never, value: 102 },
    ];

    expect(equityMarkerTime("2025-01-01T10:07:45Z", data)).toBe(
      start + 300,
    );
  });
});

import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "../../test/render";
import { ResearchNotesTab } from "./research-notes-tab";
import { SignalsDecisionsTab } from "./signals-decisions-tab";

describe("기록 경로 미구현 상태의 정직 표기", () => {
  it("조건부 기대값과 연구 노트를 우연한 빈 결과가 아닌 3차 유보로 표시한다", async () => {
    renderWithQuery(<ResearchNotesTab runId="fixture-empty" summary={null} />);

    expect(
      await screen.findByText(/이 지표는 아직 기록 경로가 미구현이라 유보되었습니다\(3차\)/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /연구 노트\(FINDING_CLAIM\)는 아직 기록 경로가 미구현이라/,
      ),
    ).toBeInTheDocument();
  });

  it("놓친 기회 섹션을 MISSED_OPPORTUNITY 기록 경로의 3차 유보로 표시한다", async () => {
    const user = userEvent.setup();
    renderWithQuery(
      <SignalsDecisionsTab runId="fixture-empty" onSelectTrade={vi.fn()} />,
    );

    await user.click(await screen.findByRole("tab", { name: /놓친 기회/ }));

    expect(
      screen.getByText(
        /놓친 기회\(MISSED_OPPORTUNITY\)는 기록 경로가 미구현이라/,
      ),
    ).toBeInTheDocument();
  });
});

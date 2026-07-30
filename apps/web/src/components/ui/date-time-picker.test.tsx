import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type FormEvent } from "react";
import { describe, expect, it, vi } from "vitest";

import { DateTimePickerField } from "./date-time-picker";

function PickerHarness({
  onSubmit = () => undefined,
}: {
  onSubmit?: (value: string) => void;
}) {
  const [value, setValue] = useState("2025-07-01T00:00");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit(value);
  }

  return (
    <form onSubmit={handleSubmit}>
      <DateTimePickerField
        value={value}
        onChange={setValue}
        aria-label="테스트 기간"
      />
      <output aria-label="확정 값">{value}</output>
      <button type="submit">제출</button>
    </form>
  );
}

describe("DateTimePickerField", () => {
  it("선택 완료 전에는 값을 유지하고 확정한 로컬 문자열을 폼 제출에 전달한다", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PickerHarness onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "테스트 기간" }));
    const dialog = screen.getByRole("dialog", { name: "테스트 기간 선택" });
    await user.click(
      within(dialog).getByRole("button", { name: "2025년 7월 15일 선택" }),
    );
    fireEvent.change(within(dialog).getByLabelText("시간"), {
      target: { value: "13:45" },
    });

    expect(screen.getByLabelText("확정 값")).toHaveTextContent(
      "2025-07-01T00:00",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "선택 완료" }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByLabelText("확정 값")).toHaveTextContent(
      "2025-07-15T13:45",
    );
    await user.click(screen.getByRole("button", { name: "제출" }));
    expect(onSubmit).toHaveBeenCalledWith("2025-07-15T13:45");
  });

  it("취소와 Esc는 편집값을 버리고 모달을 닫는다", async () => {
    const user = userEvent.setup();
    render(<PickerHarness />);

    await user.click(screen.getByRole("button", { name: "테스트 기간" }));
    let dialog = screen.getByRole("dialog", { name: "테스트 기간 선택" });
    await user.click(
      within(dialog).getByRole("button", { name: "2025년 7월 20일 선택" }),
    );
    fireEvent.change(within(dialog).getByLabelText("시간"), {
      target: { value: "08:30" },
    });
    await user.click(within(dialog).getByRole("button", { name: "취소" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByLabelText("확정 값")).toHaveTextContent(
      "2025-07-01T00:00",
    );

    await user.click(screen.getByRole("button", { name: "테스트 기간" }));
    dialog = screen.getByRole("dialog", { name: "테스트 기간 선택" });
    expect(dialog).toBeInTheDocument();
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByLabelText("확정 값")).toHaveTextContent(
      "2025-07-01T00:00",
    );
  });

  it("연도 이동 버튼으로 한 번에 12개월을 건너뛰고 그 달을 선택할 수 있다", async () => {
    const user = userEvent.setup();
    render(<PickerHarness />);

    await user.click(screen.getByRole("button", { name: "테스트 기간" }));
    const dialog = screen.getByRole("dialog", { name: "테스트 기간 선택" });
    expect(within(dialog).getByText("2025년 7월")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "다음 해" }));
    expect(within(dialog).getByText("2026년 7월")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "이전 해" }));
    await user.click(within(dialog).getByRole("button", { name: "이전 해" }));
    expect(within(dialog).getByText("2024년 7월")).toBeInTheDocument();

    await user.click(
      within(dialog).getByRole("button", { name: "2024년 7월 15일 선택" }),
    );
    await user.click(within(dialog).getByRole("button", { name: "선택 완료" }));

    expect(screen.getByLabelText("확정 값")).toHaveTextContent(
      "2024-07-15T00:00",
    );
  });

  it("PageUp/PageDown은 한 달을, Shift와 함께 누르면 한 해를 이동한다", async () => {
    const user = userEvent.setup();
    render(<PickerHarness />);

    await user.click(screen.getByRole("button", { name: "테스트 기간" }));
    const dialog = screen.getByRole("dialog", { name: "테스트 기간 선택" });

    await user.keyboard("{PageDown}");
    expect(
      within(dialog).getByRole("button", { name: "2025년 8월 1일 선택" }),
    ).toHaveFocus();

    await user.keyboard("{Shift>}{PageUp}{/Shift}");
    expect(
      within(dialog).getByRole("button", { name: "2024년 8월 1일 선택" }),
    ).toHaveFocus();
  });

  it("방향키로 날짜를 이동해 키보드 포커스와 선택 상태를 함께 갱신한다", async () => {
    const user = userEvent.setup();
    render(<PickerHarness />);

    await user.click(screen.getByRole("button", { name: "테스트 기간" }));
    const dialog = screen.getByRole("dialog", { name: "테스트 기간 선택" });
    expect(
      within(dialog).getByRole("button", { name: "2025년 7월 1일 선택" }),
    ).toHaveFocus();

    await user.keyboard("{ArrowRight}");

    const nextDate = within(dialog).getByRole("button", {
      name: "2025년 7월 2일 선택",
    });
    expect(nextDate).toHaveFocus();
    expect(nextDate.closest('[role="gridcell"]')).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});

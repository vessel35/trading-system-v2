import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { GuidedInput } from "./guided-input";

function leverageField() {
  render(
    <form>
      <GuidedInput
        aria-label="수동 레버리지"
        hint="자연수 · 1–100"
        type="number"
        min={1}
        max={100}
        step={1}
        defaultValue="1"
        required
      />
    </form>,
  );
  return screen.getByLabelText("수동 레버리지") as HTMLInputElement;
}

describe("입력 안내", () => {
  it("허용되는 값을 입력 전에 보여 주고 그 설명을 항목에 연결한다", () => {
    const input = leverageField();
    const hint = screen.getByText("자연수 · 1–100");
    expect(input).toHaveAccessibleName("수동 레버리지");
    expect(input.getAttribute("aria-describedby")).toBe(hint.id);
  });

  it("소수를 넣으면 브라우저 기본 문구 대신 규칙을 말한다", async () => {
    const user = userEvent.setup();
    const input = leverageField();
    await user.clear(input);
    await user.type(input, "1.5");

    expect(input.checkValidity()).toBe(false);
    expect(input.validationMessage).toBe("자연수만 입력 가능합니다.");
  });

  it("범위를 벗어나면 그 범위를 말한다", async () => {
    const user = userEvent.setup();
    const input = leverageField();
    await user.clear(input);
    await user.type(input, "300");

    expect(input.checkValidity()).toBe(false);
    expect(input.validationMessage).toBe("1 이상 100 이하만 입력 가능합니다.");
  });

  it("고치면 거절 상태가 그대로 남지 않는다", async () => {
    const user = userEvent.setup();
    const input = leverageField();
    await user.clear(input);
    await user.type(input, "1.5");
    expect(input.checkValidity()).toBe(false);

    await user.clear(input);
    await user.type(input, "3");
    expect(input.checkValidity()).toBe(true);
    expect(input.validationMessage).toBe("");
  });
});

import { describe, expect, it } from "vitest";

import { fieldMessage } from "./field-message";

interface FakeField {
  validity: Partial<ValidityState>;
  min?: string;
  max?: string;
  step?: string;
  title?: string;
  minLength?: number;
  maxLength?: number;
}

/** Build the minimum of an input the message function actually reads. */
function field(overrides: FakeField): HTMLInputElement {
  return {
    min: "",
    max: "",
    step: "",
    title: "",
    minLength: -1,
    maxLength: -1,
    ...overrides,
    validity: {
      valueMissing: false,
      badInput: false,
      stepMismatch: false,
      rangeUnderflow: false,
      rangeOverflow: false,
      patternMismatch: false,
      tooShort: false,
      tooLong: false,
      typeMismatch: false,
      ...overrides.validity,
    },
  } as unknown as HTMLInputElement;
}

describe("입력 거절 메시지", () => {
  it("소수를 넣은 정수 항목은 자연수만 받는다고 알린다", () => {
    expect(
      fieldMessage(
        field({ validity: { stepMismatch: true }, min: "1", max: "100", step: "1" }),
      ),
    ).toBe("자연수만 입력 가능합니다.");
  });

  it("0을 허용하는 정수 항목은 정수라고만 알린다", () => {
    expect(
      fieldMessage(
        field({ validity: { stepMismatch: true }, min: "0", step: "1" }),
      ),
    ).toBe("정수만 입력 가능합니다.");
  });

  it("범위를 벗어나면 양쪽 경계를 그대로 말한다", () => {
    expect(
      fieldMessage(
        field({ validity: { rangeOverflow: true }, min: "0.1", max: "10", step: "any" }),
      ),
    ).toBe("0.1 이상 10 이하만 입력 가능합니다.");
    expect(
      fieldMessage(field({ validity: { rangeUnderflow: true }, min: "0", step: "any" })),
    ).toBe("0 이상만 입력 가능합니다.");
  });

  it("경계 바로 안쪽 값은 초과·미만으로 읽어 준다", () => {
    // HTML은 포함 경계만 표현하므로 "0 초과"는 아주 작은 양수로 적어 둔다.
    expect(
      fieldMessage(
        field({
          validity: { rangeUnderflow: true },
          min: "0.000000000001",
          max: "0.01",
        }),
      ),
    ).toBe("0 초과 0.01 이하만 입력 가능합니다.");
    expect(
      fieldMessage(
        field({
          validity: { rangeOverflow: true },
          min: "0.000000000001",
          max: "0.999999999999",
        }),
      ),
    ).toBe("0 초과 1 미만만 입력 가능합니다.");
  });

  it("숫자가 아닌 입력과 빈 값을 구분한다", () => {
    expect(fieldMessage(field({ validity: { badInput: true } }))).toBe(
      "숫자만 입력 가능합니다.",
    );
    expect(fieldMessage(field({ validity: { valueMissing: true } }))).toBe(
      "필수 입력 항목입니다.",
    );
  });

  it("형식 오류는 그 항목이 설명한 형식을 그대로 보여 준다", () => {
    expect(
      fieldMessage(
        field({
          validity: { patternMismatch: true },
          title: "BASE/QUOTE 또는 BASE/QUOTE:SETTLE 형식으로 입력 가능합니다.",
        }),
      ),
    ).toBe("BASE/QUOTE 또는 BASE/QUOTE:SETTLE 형식으로 입력 가능합니다.");
  });
});

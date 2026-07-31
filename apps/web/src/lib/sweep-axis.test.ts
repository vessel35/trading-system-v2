import { describe, expect, it } from "vitest";

import {
  axisValuesError,
  axisValuesHint,
  defaultAxisValues,
} from "./sweep-axis";

describe("스윕 축 값 규칙", () => {
  it("정수 파라미터는 정수 예시로 시작한다", () => {
    expect(defaultAxisValues("money_management.leverage", "[1.5, 2.0]")).toBe(
      "[1, 2, 3]",
    );
    expect(defaultAxisValues("money_management.n_period", "[1.5]")).toBe(
      "[10, 20, 40]",
    );
  });

  it("소수 파라미터와 규칙 없는 파라미터는 각자의 값을 유지한다", () => {
    expect(defaultAxisValues("money_management.reward_risk", "[9]")).toBe(
      "[1.5, 2, 2.5]",
    );
    expect(defaultAxisValues("ema_fast", "[10, 20]")).toBe("[10, 20]");
  });

  it("정수 파라미터에 소수를 쓰면 그 이유를 축 이름과 함께 말한다", () => {
    expect(
      axisValuesError("money_management.leverage", [1.5, 2, 2.5], "첫 번째 축"),
    ).toBe("첫 번째 축의 money_management.leverage 값은 자연수만 가능합니다 (1–100).");
  });

  it("범위를 벗어난 값도 걸러 낸다", () => {
    expect(
      axisValuesError("money_management.leverage", [1, 2, 300], "두 번째 축"),
    ).toBe("두 번째 축의 money_management.leverage 값은 1 이상 100 이하만 가능합니다.");
    expect(
      axisValuesError("money_management.reward_risk", [0.05, 1], "첫 번째 축"),
    ).toBe("첫 번째 축의 money_management.reward_risk 값은 0.1 이상 10 이하만 가능합니다.");
  });

  it("규칙을 만족하거나 규칙이 없는 축은 통과시킨다", () => {
    expect(
      axisValuesError("money_management.leverage", [1, 2, 3], "첫 번째 축"),
    ).toBeNull();
    expect(axisValuesError("ema_fast", [10, 20], "첫 번째 축")).toBeNull();
  });

  it("안내 문구가 그 파라미터의 종류와 범위를 말한다", () => {
    expect(axisValuesHint("money_management.leverage")).toBe(
      "JSON 배열 · 값 2–20개 · 자연수 1–100",
    );
    expect(axisValuesHint("money_management.reward_risk")).toBe(
      "JSON 배열 · 값 2–20개 · 소수 가능 0.1–10",
    );
    expect(axisValuesHint("ema_fast")).toBe("JSON 배열 · 값 2–20개");
  });
});

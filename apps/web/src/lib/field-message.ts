/**
 * Turn a rejected field into one plain sentence saying what may be typed.
 *
 * The browser's own text ("값이 유효하지 않습니다. 가장 근접한 값은 …") describes
 * the failure rather than the rule, so every message here states the rule: which
 * kind of number the field takes and, when it is bounded, the range. The rule is
 * read from the element's own min, max, and step, so a message can never drift
 * from the constraint the form actually enforces.
 */

function trimNumber(value: string): string {
  if (!value) return value;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  // 0.000000000001 stands in for "greater than zero"; showing it would be noise.
  return String(parsed);
}

/** HTML bounds are inclusive, so an exclusive limit is written just inside it. */
const EXCLUSIVE_MARGIN = 1e-6;

function lowerPhrase(min: string): string | null {
  if (!min) return null;
  const value = Number(min);
  if (!Number.isFinite(value)) return null;
  if (value > 0 && value < EXCLUSIVE_MARGIN) return "0 초과";
  return `${trimNumber(min)} 이상`;
}

function upperPhrase(max: string): string | null {
  if (!max) return null;
  const value = Number(max);
  if (!Number.isFinite(value)) return null;
  const ceiling = Math.ceil(value);
  const gap = ceiling - value;
  if (gap > 0 && gap < EXCLUSIVE_MARGIN) return `${ceiling} 미만`;
  return `${trimNumber(max)} 이하`;
}

function rangePhrase(min: string, max: string): string {
  const low = lowerPhrase(min);
  const high = upperPhrase(max);
  if (low && high) return `${low} ${high}만 입력 가능합니다.`;
  if (low) return `${low}만 입력 가능합니다.`;
  if (high) return `${high}만 입력 가능합니다.`;
  return "입력 가능한 범위를 벗어났습니다.";
}

function wholeNumberPhrase(min: string): string {
  const low = Number(min);
  // A field whose smallest accepted value is at least one takes natural numbers;
  // one that also accepts zero or negatives takes integers.
  return Number.isFinite(low) && low >= 1
    ? "자연수만 입력 가능합니다."
    : "정수만 입력 가능합니다.";
}

/** Return the message to show for one rejected input. */
export function fieldMessage(input: HTMLInputElement): string {
  const validity = input.validity;
  const { min, max, step } = input;

  if (validity.valueMissing) return "필수 입력 항목입니다.";
  if (validity.badInput) return "숫자만 입력 가능합니다.";
  if (validity.stepMismatch) {
    if (step === "" || step === "1") return wholeNumberPhrase(min);
    return `${trimNumber(step)} 단위로 입력 가능합니다.`;
  }
  if (validity.rangeUnderflow || validity.rangeOverflow) return rangePhrase(min, max);
  if (validity.patternMismatch) {
    return input.title || "입력 형식이 올바르지 않습니다.";
  }
  if (validity.tooShort) return `${input.minLength}자 이상 입력해 주세요.`;
  if (validity.tooLong) return `${input.maxLength}자 이하로 입력해 주세요.`;
  if (validity.typeMismatch) return input.title || "입력 형식이 올바르지 않습니다.";
  return "입력값을 확인해 주세요.";
}

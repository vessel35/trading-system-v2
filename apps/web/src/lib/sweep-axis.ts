/**
 * What each sweep axis may vary, and with which values.
 *
 * A sweep builds one run per combination, and every one of those runs is
 * validated by the same schema as a single run. So an axis over an integer
 * parameter has to carry integers: leverage swept as [1.5, 2.0, 2.5] produces
 * runs the server rejects, one combination at a time. The rules below mirror the
 * run-configuration schema so the form can offer valid values from the start and
 * explain the rule before the sweep is submitted.
 */

export interface AxisValueRule {
  /** Whole numbers only, as the schema declares the parameter an integer. */
  integer: boolean;
  min: number;
  max: number;
  /** A starting set of values that satisfies the rule. */
  example: readonly number[];
}

const AXIS_VALUE_RULES: Readonly<Record<string, AxisValueRule>> = {
  "money_management.leverage": { integer: true, min: 1, max: 100, example: [1, 2, 3] },
  "money_management.leverage_cap": {
    integer: true,
    min: 1,
    max: 100,
    example: [5, 10, 20],
  },
  "money_management.n_period": {
    integer: true,
    min: 2,
    max: 200,
    example: [10, 20, 40],
  },
  "money_management.reward_risk": {
    integer: false,
    min: 0.1,
    max: 10,
    example: [1.5, 2.0, 2.5],
  },
  "money_management.atr_stop_multiple": {
    integer: false,
    min: 0.1,
    max: 10,
    example: [1.5, 2.0, 2.5],
  },
  "money_management.stop_n_multiple": {
    integer: false,
    min: 0.1,
    max: 10,
    example: [1.5, 2.0, 2.5],
  },
};

/** Return the rule for one axis parameter, or null when it carries no bounds. */
export function axisValueRule(parameter: string): AxisValueRule | null {
  return AXIS_VALUE_RULES[parameter.trim()] ?? null;
}

/** Return the JSON text a freshly chosen parameter should start from. */
export function defaultAxisValues(parameter: string, fallback: string): string {
  const rule = axisValueRule(parameter);
  return rule ? `[${rule.example.join(", ")}]` : fallback;
}

/** Describe the accepted values of one axis in a single line. */
export function axisValuesHint(parameter: string): string {
  const rule = axisValueRule(parameter);
  if (!rule) return "JSON 배열 · 값 2–20개";
  const kind = rule.integer ? "자연수" : "소수 가능";
  return `JSON 배열 · 값 2–20개 · ${kind} ${rule.min}–${rule.max}`;
}

/**
 * Return why these values cannot be swept over this parameter, or null.
 *
 * Checking here rather than letting the server answer means the reader is told
 * which axis and which value is wrong instead of receiving one schema error for
 * a combination they never typed.
 */
export function axisValuesError(
  parameter: string,
  values: readonly (string | number | boolean)[],
  label: string,
): string | null {
  const rule = axisValueRule(parameter);
  if (!rule) return null;
  for (const value of values) {
    if (typeof value !== "number") {
      return `${label}의 ${parameter} 값은 숫자여야 합니다.`;
    }
    if (rule.integer && !Number.isInteger(value)) {
      return `${label}의 ${parameter} 값은 자연수만 가능합니다 (${rule.min}–${rule.max}).`;
    }
    if (value < rule.min || value > rule.max) {
      return `${label}의 ${parameter} 값은 ${rule.min} 이상 ${rule.max} 이하만 가능합니다.`;
    }
  }
  return null;
}

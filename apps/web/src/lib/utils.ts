import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function formatPeriod(start: string, end: string): string {
  const formatter = new Intl.DateTimeFormat("ko-KR", {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    timeZone: "UTC",
  });
  return `${formatter.format(new Date(start))} → ${formatter.format(new Date(end))}`;
}

export function formatMetric(
  value: number | null | undefined,
  options?: Intl.NumberFormatOptions,
): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 3,
    ...options,
  }).format(value);
}

export function formatDecimalString(value: string | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const match = /^(-?)(\d+)(\.\d+)?$/.exec(value);
  if (!match) {
    return value;
  }
  const [, sign, integer, fraction = ""] = match;
  return `${sign}${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction}`;
}

export function formatRatioPercent(value: string | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const match = /^(-?)(\d+)(?:\.(\d{4}))?$/.exec(value);
  if (!match) {
    return value;
  }
  const [, sign, integer, fraction = "0000"] = match;
  const digits = `${integer}${fraction}`;
  const decimalPosition = integer.length + 2;
  const whole = digits.slice(0, decimalPosition).replace(/^0+(?=\d)/, "");
  const decimal = digits.slice(decimalPosition).padEnd(2, "0");
  return `${sign}${whole}.${decimal}%`;
}

export function catalogDecisionPresentation(
  summaryPresent: boolean,
  gateVerdict: string | null,
  decisionRoute: string | null,
): { label: string; showRoute: boolean } {
  return {
    label: summaryPresent ? (gateVerdict ?? decisionRoute ?? "—") : "요약 없음",
    showRoute:
      summaryPresent && gateVerdict !== null && decisionRoute !== null,
  };
}

export function shortHash(value: string | null | undefined, length = 10): string {
  if (!value) {
    return "—";
  }
  return `${value.slice(0, length)}…`;
}

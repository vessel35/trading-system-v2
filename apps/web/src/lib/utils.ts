import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

// Every timestamp the console shows or accepts is Korea Standard Time. Timestamps are
// stored and exchanged as UTC instants; only the presentation is converted, and it is
// converted in one place so a value entered on one screen reads the same on another.
export const DISPLAY_TIME_ZONE = "Asia/Seoul";

export function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: DISPLAY_TIME_ZONE,
  }).format(new Date(value));
}

export function formatPeriod(start: string, end: string): string {
  const formatter = new Intl.DateTimeFormat("ko-KR", {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    timeZone: DISPLAY_TIME_ZONE,
  });
  return `${formatter.format(new Date(start))} → ${formatter.format(new Date(end))}`;
}

const displayZoneParts = new Intl.DateTimeFormat("en-CA", {
  timeZone: DISPLAY_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  // h23 rather than hour12:false: the latter renders midnight as hour 24, which both
  // produces an unparseable field value and shifts the offset this module derives.
  hourCycle: "h23",
});

/** Render a UTC instant as the `YYYY-MM-DDTHH:mm` wall clock of the display zone. */
export function toDisplayZoneInput(value: string): string {
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) {
    return "";
  }
  const parts = new Map(
    displayZoneParts.formatToParts(instant).map((part) => [part.type, part.value]),
  );
  const date = `${parts.get("year")}-${parts.get("month")}-${parts.get("day")}`;
  return `${date}T${parts.get("hour")}:${parts.get("minute")}`;
}

const wallClockPattern = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

/** Read a `YYYY-MM-DDTHH:mm` wall clock in the display zone and return its UTC instant. */
export function fromDisplayZoneInput(value: string): Date {
  // The shape is checked before parsing because Date accepts a good deal of nonsense:
  // `new Date("not-a-time:00Z")` yields the year 2000 rather than an invalid date.
  const match = wallClockPattern.exec(value);
  if (!match) {
    return new Date(Number.NaN);
  }
  const [, year, month, day, hour, minute] = match;
  const naive = new Date(Date.UTC(+year, +month - 1, +day, +hour, +minute));
  // A rolled-over date such as 2026-02-31 is rejected rather than silently shifted.
  if (naive.getUTCMonth() !== +month - 1 || naive.getUTCDate() !== +day) {
    return new Date(Number.NaN);
  }
  // The offset is taken from the zone at that moment rather than hard-coded, so this
  // stays correct if the display zone is ever changed to one that observes DST.
  const parts = new Map(
    displayZoneParts.formatToParts(naive).map((part) => [part.type, part.value]),
  );
  const asZone = Date.UTC(
    Number(parts.get("year")),
    Number(parts.get("month")) - 1,
    Number(parts.get("day")),
    Number(parts.get("hour")),
    Number(parts.get("minute")),
    Number(parts.get("second")),
  );
  return new Date(naive.getTime() - (asZone - naive.getTime()));
}

const chartTickFormatter = new Intl.DateTimeFormat("ko-KR", {
  timeZone: DISPLAY_TIME_ZONE,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/**
 * Label a chart time axis in the display zone.
 *
 * The charting library places ticks in UTC, so without this the price and equity axes
 * would read nine hours off every table on the same screen.
 */
export function formatChartTime(epochSeconds: number): string {
  return chartTickFormatter.format(new Date(epochSeconds * 1_000));
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

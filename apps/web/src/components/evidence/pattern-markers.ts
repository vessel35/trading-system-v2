import type { SeriesMarker, UTCTimestamp } from "lightweight-charts";

import type { IndicatorSnapshot } from "../../api/client";

export type PatternEventKind = "occurrence" | "confirmation";

export interface PatternEvent {
  key: string;
  name: string;
  implVersion: string;
  candleOpenTime: string;
  kind: PatternEventKind;
  strength: 0 | 0.5 | 1;
  rawDirection: -1 | 1;
}

export interface PatternMarkerGroup {
  id: string;
  time: UTCTimestamp;
  marker: SeriesMarker<UTCTimestamp>;
  events: PatternEvent[];
}

export function seriesLabel(key: string, implVersion: string): string {
  return `${key} (${implVersion})`;
}

function utcSeconds(value: string): UTCTimestamp {
  return Math.floor(new Date(value).getTime() / 1_000) as UTCTimestamp;
}

function patternEvent(snapshot: IndicatorSnapshot): PatternEvent | null {
  if (
    snapshot.series_kind !== "pattern" ||
    typeof snapshot.value_json !== "object" ||
    snapshot.value_json === null ||
    Array.isArray(snapshot.value_json)
  ) {
    return null;
  }
  const values = snapshot.value_json as Record<string, unknown>;
  const occurred = values.occurred === 1;
  const confirmed = values.confirmed === 1;
  if (occurred === confirmed) return null;

  const rawDirection = values.direction;
  const strength = values.strength;
  if (rawDirection !== -1 && rawDirection !== 1) return null;
  if (confirmed) {
    if (strength !== 0) return null;
  } else if (strength !== 0.5 && strength !== 1) {
    return null;
  }
  return {
    key: snapshot.indicator_key,
    name: snapshot.indicator_name,
    implVersion: snapshot.impl_version,
    candleOpenTime: snapshot.candle_open_time,
    kind: confirmed ? "confirmation" : "occurrence",
    strength,
    rawDirection,
  };
}

function markerText(events: PatternEvent[]): string {
  if (events.length > 1) {
    const kinds = new Set(events.map((event) => event.kind));
    const kind =
      kinds.size > 1
        ? "성립·확인"
        : events[0].kind === "confirmation"
          ? "확인"
          : "성립";
    return `패턴 ${events.length} · ${kind}`;
  }
  const [event] = events;
  if (event.kind === "confirmation") return "확인";
  const kind = "성립";
  const strength = event.strength === 0.5 ? "경계 0.5" : "강도 1.0";
  return `${kind} · ${strength}`;
}

function markerColor(events: PatternEvent[]): string {
  const strengths = new Set(events.map((event) => event.strength));
  if (strengths.size > 1) return "#c084fc";
  if (events[0].strength === 0.5) return "#f59e0b";
  return events.every((event) => event.kind === "confirmation")
    ? "#22d3ee"
    : "#a78bfa";
}

export function buildPatternMarkerGroups(
  snapshots: IndicatorSnapshot[],
): PatternMarkerGroup[] {
  const eventsByCandle = new Map<string, PatternEvent[]>();
  snapshots.forEach((snapshot) => {
    const event = patternEvent(snapshot);
    if (event === null) return;
    const events = eventsByCandle.get(event.candleOpenTime) ?? [];
    events.push(event);
    eventsByCandle.set(event.candleOpenTime, events);
  });

  return [...eventsByCandle]
    .map(([candleOpenTime, unsortedEvents]) => {
      const events = [...unsortedEvents].sort((left, right) =>
        left.key.localeCompare(right.key),
      );
      const time = utcSeconds(candleOpenTime);
      const id = `pattern:${Number(time)}`;
      return {
        id,
        time,
        events,
        marker: {
          id,
          time,
          position: "aboveBar",
          color: markerColor(events),
          shape: events.some((event) => event.kind === "confirmation")
            ? "square"
            : "circle",
          text: markerText(events),
        },
      } satisfies PatternMarkerGroup;
    })
    .sort((left, right) => Number(left.time) - Number(right.time));
}

export function patternEventDescription(event: PatternEvent): string {
  const kind = event.kind === "confirmation" ? "확인" : "성립";
  const sign = event.rawDirection > 0 ? "+1" : "-1";
  const strength =
    event.kind === "confirmation"
      ? "강도 해당 없음"
      : `강도 ${event.strength.toFixed(1)}`;
  return `${seriesLabel(event.key, event.implVersion)} · ${kind} · ${strength} · TA-Lib 원시 부호 ${sign} · 매매 방향 아님`;
}

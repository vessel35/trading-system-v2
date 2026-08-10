import type { UTCTimestamp } from "lightweight-charts";

export type EquityDatum = { time: UTCTimestamp; value: number };

export interface EquitySourcePoint {
  timestamp: string;
  value: number;
}

export interface ProjectedEquitySeries {
  points: EquityDatum[];
  sourcePointCount: number;
  foldedPointCount: number;
}

/** Project ordered Evidence timestamps onto the chart's second-resolution axis. */
export function projectEquitySeries(
  source: readonly EquitySourcePoint[],
): ProjectedEquitySeries {
  const points: EquityDatum[] = [];

  source.forEach(({ timestamp, value }) => {
    const point = {
      time: Math.floor(new Date(timestamp).getTime() / 1_000) as UTCTimestamp,
      value,
    };
    const previous = points.at(-1);
    if (previous?.time === point.time) {
      points[points.length - 1] = point;
    } else {
      points.push(point);
    }
  });

  return {
    points,
    sourcePointCount: source.length,
    foldedPointCount: source.length - points.length,
  };
}

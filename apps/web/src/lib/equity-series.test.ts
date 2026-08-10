import { describe, expect, it } from "vitest";

import { projectEquitySeries } from "./equity-series";

describe("자본 Evidence의 초 단위 차트 투영", () => {
  it("같은 초에 세 점이 있으면 마지막 값 하나만 남긴다", () => {
    const projected = projectEquitySeries([
      { timestamp: "2025-07-03T14:55:00.000Z", value: 8_010 },
      { timestamp: "2025-07-03T15:00:00.000Z", value: 7_994.92543575 },
      { timestamp: "2025-07-03T15:00:00.001Z", value: 7_993 },
      { timestamp: "2025-07-03T15:00:00.999Z", value: 7_992.65787561 },
    ]);

    expect(projected).toEqual({
      points: [
        { time: Date.parse("2025-07-03T14:55:00Z") / 1_000, value: 8_010 },
        {
          time: Date.parse("2025-07-03T15:00:00Z") / 1_000,
          value: 7_992.65787561,
        },
      ],
      sourcePointCount: 4,
      foldedPointCount: 2,
    });
  });

  it("겹치지 않는 점의 시각과 값과 개수를 그대로 둔다", () => {
    const source = [
      { timestamp: "2025-07-03T14:55:00.000Z", value: 8_010 },
      { timestamp: "2025-07-03T15:00:00.000Z", value: 7_994.92543575 },
    ];

    expect(projectEquitySeries(source)).toEqual({
      points: [
        { time: Date.parse(source[0].timestamp) / 1_000, value: source[0].value },
        { time: Date.parse(source[1].timestamp) / 1_000, value: source[1].value },
      ],
      sourcePointCount: source.length,
      foldedPointCount: 0,
    });
  });
});

import { http, HttpResponse } from "msw";

import type { Signal } from "../../api/client";

export const emptyEvidenceFixture = {
  data: [],
  page: {
    limit: 200,
    after_seq: 0,
    next_after_seq: null,
    total: 0,
    has_more: false,
  },
} as const;

export const standardErrorFixture = {
  error: {
    code: "fixture_evidence_error",
    message: "표준 Evidence 오류 픽스처",
  },
} as const;

export const LARGE_EVIDENCE_TOTAL = 5_200;

function signal(signalId: number): Signal {
  const minute = String(signalId % 60).padStart(2, "0");
  const timestamp = `2025-01-01T00:${minute}:00Z`;
  return {
    signal_id: signalId,
    run_id: "fixture-large",
    decision_ts: timestamp,
    feature_ts: timestamp,
    candle_open_time: timestamp,
    candle_close_time: timestamp,
    symbol: "BTC/USDT:USDT",
    price: 100,
    confidence: 0.5,
    stop_loss: null,
    take_profit: null,
    market_type: "futures",
    leverage: null,
    reason: "large fixture",
    metadata_json: null,
    derived_intent: "hold",
    derived_side: null,
    is_warmup: false,
  };
}

const emptyCursorResources = [
  "chart-summaries",
  "equity",
  "executions",
  "drawdown-episodes",
  "signals",
  "decisions",
  "candidate-events",
  "missed-opportunities",
  "conditional-expectancy",
  "findings",
  "trades",
  "outcome-buckets",
  "integrity-checks",
  "indicator-snapshots",
] as const;

export const emptyEvidenceHandlers = [
  ...emptyCursorResources.map((resource) =>
    http.get(`http://localhost/api/v1/runs/:runId/${resource}`, () =>
      HttpResponse.json(emptyEvidenceFixture),
    ),
  ),
  http.get("http://localhost/api/v1/runs/:runId/prereg", () =>
    HttpResponse.json({ run_id: "fixture-empty", prereg: null }),
  ),
];

export const standardErrorHandlers = [
  http.get("http://localhost/api/v1/runs/:runId/signals", () =>
    HttpResponse.json(standardErrorFixture, { status: 503 }),
  ),
];

export const largeEvidenceHandlers = [
  http.get("http://localhost/api/v1/runs/:runId/signals", ({ request }) => {
    const afterSeq = Number(new URL(request.url).searchParams.get("after_seq") ?? 0);
    const nextAfterSeq = Math.min(afterSeq + 200, LARGE_EVIDENCE_TOTAL);
    const data = Array.from(
      { length: nextAfterSeq - afterSeq },
      (_, index) => signal(afterSeq + index + 1),
    );
    const hasMore = nextAfterSeq < LARGE_EVIDENCE_TOTAL;
    return HttpResponse.json({
      data,
      page: {
        limit: 200,
        after_seq: afterSeq,
        next_after_seq: hasMore ? nextAfterSeq : null,
        total: LARGE_EVIDENCE_TOTAL,
        has_more: hasMore,
      },
    });
  }),
];

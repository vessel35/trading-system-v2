import { AlertTriangle, DatabaseZap } from "lucide-react";

import { ApiRequestError, isEvidenceUnavailable } from "../../api/client";
import {
  EVIDENCE_PAGE_LIMIT,
  EVIDENCE_ROW_LIMIT,
  isTruncatedEvidence,
  type EvidencePage,
} from "../../hooks/use-evidence";
import { Badge } from "../ui/badge";
import { Card, CardContent } from "../ui/card";
import { Skeleton } from "../ui/skeleton";

export function EvidenceLoading() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-72 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

export function EvidenceError({ error }: { error: unknown }) {
  const unavailable = isEvidenceUnavailable(error);
  const code = error instanceof ApiRequestError ? error.code : null;
  return (
    <Card>
      <CardContent className="grid min-h-64 place-items-center p-8 text-center">
        <div>
          <DatabaseZap className="mx-auto h-8 w-8 text-amber-400" />
          <p className="mt-3 font-medium">
            {unavailable ? "상세 증거 접근 불가 · 요약만" : "Evidence를 불러오지 못했습니다."}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "잠시 뒤 다시 시도해 주세요."}
          </p>
          {code && (
            <Badge variant="outline" className="mt-3 font-mono">
              {code}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function EvidenceTruncationNotice({
  sources,
}: {
  sources: Array<EvidencePage<unknown> | null | undefined>;
}) {
  if (!sources.some(isTruncatedEvidence)) return null;
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-sm text-amber-100"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        Evidence 안전 상한 {EVIDENCE_ROW_LIMIT.toLocaleString()}행 또는{" "}
        {EVIDENCE_PAGE_LIMIT.toLocaleString()}페이지에서 조회를 중단했습니다. 표시된 결과는
        일부이며, 전체를 확인하려면 API 조회 조건이나 기간을 좁히세요.
      </p>
    </div>
  );
}

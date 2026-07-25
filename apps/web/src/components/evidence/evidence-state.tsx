import { DatabaseZap } from "lucide-react";

import { isEvidenceUnavailable } from "../../api/client";
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
        </div>
      </CardContent>
    </Card>
  );
}

import createClient from "openapi-fetch";

import type { components, operations, paths } from "./schema";

export const apiClient = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
});

export type RunListItem = components["schemas"]["RunListItem"];
export type RunListResponse = components["schemas"]["RunListResponse"];
export type RunHeader = components["schemas"]["RunHeader"];
export type RunSummaryResponse = components["schemas"]["RunSummaryResponse"];
export type RunSummary = components["schemas"]["RunSummary"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type RunQuery = NonNullable<
  operations["list_runs_api_v1_runs_get"]["parameters"]["query"]
>;

export function requestErrorMessage(error: unknown): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "error" in error &&
    typeof error.error === "object" &&
    error.error !== null &&
    "message" in error.error &&
    typeof error.error.message === "string"
  ) {
    return error.error.message;
  }
  return "카탈로그 요청을 완료하지 못했습니다.";
}

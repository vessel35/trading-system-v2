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
export type Trade = components["schemas"]["Trade"];
export type Execution = components["schemas"]["Execution"];
export type FundingSettlement = components["schemas"]["FundingSettlement"];
export type EquityPoint = components["schemas"]["EquityPoint"];
export type ChartSummary = components["schemas"]["ChartSummary"];
export type Position = components["schemas"]["Position"];
export type IntegrityCheck = components["schemas"]["IntegrityCheck"];
export type OutcomeBucket = components["schemas"]["OutcomeBucket"];
export type DrawdownEpisode = components["schemas"]["DrawdownEpisode"];
export type TradeFeature = components["schemas"]["TradeFeature"];
export type CandidateEvent = components["schemas"]["CandidateEvent"];
export type Candle = components["schemas"]["Candle"];
export type CandleCollection = components["schemas"]["CandleCollection"];
export type Signal = components["schemas"]["Signal"];
export type Decision = components["schemas"]["Decision"];
export type IndicatorSnapshot = components["schemas"]["IndicatorSnapshot"];
export type MissedOpportunity = components["schemas"]["MissedOpportunity"];
export type ConditionalExpectancy = components["schemas"]["ConditionalExpectancy"];
export type Finding = components["schemas"]["Finding"];
export type Preregistration = components["schemas"]["Preregistration"];
export type PreregistrationResponse =
  components["schemas"]["PreregistrationResponse"];
export type RunComparisonItem = components["schemas"]["RunComparisonItem"];
export type RunComparisonResponse = components["schemas"]["RunComparisonResponse"];
export type RunQuery = NonNullable<
  operations["list_runs_api_v1_runs_get"]["parameters"]["query"]
>;

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly code: string | null,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

function errorDetails(error: unknown): { message: string; code: string | null } {
  if (
    typeof error === "object" &&
    error !== null &&
    "error" in error &&
    typeof error.error === "object" &&
    error.error !== null
  ) {
    const message =
      "message" in error.error && typeof error.error.message === "string"
        ? error.error.message
        : "카탈로그 요청을 완료하지 못했습니다.";
    const code =
      "code" in error.error && typeof error.error.code === "string"
        ? error.error.code
        : null;
    return { message, code };
  }
  return { message: "카탈로그 요청을 완료하지 못했습니다.", code: null };
}

export function requestErrorMessage(error: unknown): string {
  return errorDetails(error).message;
}

export function apiRequestError(error: unknown): ApiRequestError {
  const details = errorDetails(error);
  return new ApiRequestError(details.message, details.code);
}

export function isEvidenceUnavailable(error: unknown): boolean {
  return error instanceof ApiRequestError && error.code === "evidence_unavailable";
}

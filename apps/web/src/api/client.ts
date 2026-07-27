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
export type RunConfigInput =
  operations["validate_run_config_api_v1_run_config_validate_post"]["requestBody"]["content"]["application/json"];
export type RunSubmission = components["schemas"]["RunSubmission"];
export type RunAccepted = components["schemas"]["RunAccepted"];
export type JobStatus = components["schemas"]["JobStatus"];
export type SweepSubmission = components["schemas"]["SweepSubmission"];
export type SweepResponse = components["schemas"]["SweepResponse"];
export type SweepAxis = components["schemas"]["SweepAxis"];
export type BacktestTag = components["schemas"]["BacktestTag"];
export type RunTagsResponse = components["schemas"]["RunTagsResponse"];
export type TagInput = components["schemas"]["TagInput"];
export type TagFacetsResponse = components["schemas"]["TagFacetsResponse"];
export type DataSourceCoverage = components["schemas"]["DataSourceCoverage"];
export type DataSourceInventory = components["schemas"]["DataSourceInventory"];
export type InventoryItem = components["schemas"]["InventoryItem"];
export type StrategyOption = components["schemas"]["StrategyOption"];
export type StrategyListResponse = components["schemas"]["StrategyListResponse"];
export type PreregistrationInput = components["schemas"]["PreregistrationInput"];
export type RunQuery = NonNullable<
  operations["list_runs_api_v1_runs_get"]["parameters"]["query"]
>;

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly code: string | null,
    readonly violations: string[] = [],
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

interface RequestErrorDetails {
  message: string;
  code: string | null;
  violations: string[];
}

function validationViolations(details: unknown): string[] {
  if (!Array.isArray(details)) return [];
  return details.flatMap((detail) => {
    if (typeof detail !== "object" || detail === null) return [];
    const field =
      "field" in detail && typeof detail.field === "string" ? detail.field : null;
    const message =
      "message" in detail && typeof detail.message === "string"
        ? detail.message
        : null;
    if (!message) return [];
    return [`${field ? `${field}: ` : ""}${message}`];
  });
}

function errorDetails(error: unknown): RequestErrorDetails {
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
    const violations =
      "details" in error.error ? validationViolations(error.error.details) : [];
    return { message, code, violations };
  }
  return {
    message: "카탈로그 요청을 완료하지 못했습니다.",
    code: null,
    violations: [],
  };
}

export function requestErrorMessage(error: unknown): string {
  const details = errorDetails(error);
  return [
    details.message,
    ...details.violations.map((violation) => `• ${violation}`),
  ].join("\n");
}

export function apiRequestError(error: unknown): ApiRequestError {
  const details = errorDetails(error);
  return new ApiRequestError(details.message, details.code, details.violations);
}

export function isEvidenceUnavailable(error: unknown): boolean {
  return error instanceof ApiRequestError && error.code === "evidence_unavailable";
}

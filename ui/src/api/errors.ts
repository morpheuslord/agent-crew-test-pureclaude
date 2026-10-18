/** An error response from the API, or a failure to reach it (status 503). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isValidation(): boolean {
    return this.status === 422 || this.status === 409;
  }
}

interface ErrorBody {
  error?: { code?: unknown; message?: unknown; fields?: unknown };
}

function stringRecord(value: unknown): Record<string, string> {
  if (typeof value !== "object" || value === null) {
    return {};
  }
  const entries = Object.entries(value as Record<string, unknown>).filter(
    (entry): entry is [string, string] => typeof entry[1] === "string",
  );
  return Object.fromEntries(entries);
}

/** Build an ApiError from a parsed error body, tolerating unexpected shapes. */
export function apiErrorFrom(status: number, body: unknown): ApiError {
  const error = (body as ErrorBody | null)?.error;
  const code = typeof error?.code === "string" ? error.code : "error";
  const message =
    typeof error?.message === "string" ? error.message : `API error ${String(status)}`;
  return new ApiError(status, code, message, stringRecord(error?.fields));
}

import { z } from "zod";

const booleanString = z.enum(["true", "false"]).transform((value) => value === "true");

const schema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),
  HOST: z.string().min(1).default("127.0.0.1"),
  API_BASE_URL: z.url(),
  SERVICE_TOKEN: z.string().min(32, "SERVICE_TOKEN must be at least 32 characters"),
  UI_SECRET: z.string().min(32, "UI_SECRET must be at least 32 characters"),
  PUBLIC_URL: z.url(),
  COOKIE_SECURE: booleanString.default(true),
  TRUST_PROXY: z.coerce.number().int().min(0).max(5).default(0),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
  API_REQUEST_TIMEOUT_MS: z.coerce.number().int().min(100).max(60_000).default(10_000),
  MAX_UPLOAD_BYTES: z.coerce
    .number()
    .int()
    .min(1)
    .default(10 * 1024 * 1024),
});

/** Validated configuration of the UI server. */
export interface AppConfig {
  port: number;
  host: string;
  apiBaseUrl: string;
  serviceToken: string;
  uiSecret: string;
  publicOrigin: string;
  cookieSecure: boolean;
  trustProxy: number;
  logLevel: "debug" | "info" | "warn" | "error";
  apiTimeoutMs: number;
  maxUploadBytes: number;
}

/** Parse and validate environment variables. Throws with every problem listed. */
export function loadConfig(env: Record<string, string | undefined>): AppConfig {
  const result = schema.safeParse(env);
  if (!result.success) {
    const problems = result.error.issues
      .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
      .join("; ");
    throw new Error(`invalid configuration: ${problems}`);
  }
  const value = result.data;
  return {
    port: value.PORT,
    host: value.HOST,
    apiBaseUrl: value.API_BASE_URL.replace(/\/+$/, ""),
    serviceToken: value.SERVICE_TOKEN,
    uiSecret: value.UI_SECRET,
    publicOrigin: new URL(value.PUBLIC_URL).origin,
    cookieSecure: value.COOKIE_SECURE,
    trustProxy: value.TRUST_PROXY,
    logLevel: value.LOG_LEVEL,
    apiTimeoutMs: value.API_REQUEST_TIMEOUT_MS,
    maxUploadBytes: value.MAX_UPLOAD_BYTES,
  };
}

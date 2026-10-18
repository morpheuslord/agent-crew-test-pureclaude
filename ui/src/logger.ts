import { AsyncLocalStorage } from "node:async_hooks";
import { pino, type DestinationStream, type Logger } from "pino";

/** Per-request values available to every log line. */
export interface RequestContext {
  requestId: string;
}

export const requestContext = new AsyncLocalStorage<RequestContext>();

/** Structured JSON logger that stamps each line with the current request id. */
export function createLogger(level: string, destination?: DestinationStream): Logger {
  return pino(
    {
      level,
      messageKey: "message",
      base: { service: "ui" },
      timestamp: pino.stdTimeFunctions.isoTime,
      formatters: { level: (label) => ({ level: label }) },
      mixin: () => ({ request_id: requestContext.getStore()?.requestId ?? "-" }),
      redact: {
        paths: ["password", "token", "cookie", "*.password", "*.token", "*.cookie"],
        censor: "[redacted]",
      },
    },
    destination,
  );
}

import type { Express } from "express";
import type { Logger } from "pino";
import { TaskboardApiClient } from "./api/TaskboardApiClient.js";
import { createApp } from "./app.js";
import type { AppConfig } from "./config.js";

/** Composition root: the only place the concrete API client is chosen. */
export function composeApp(config: AppConfig, logger: Logger): Express {
  const api = new TaskboardApiClient({
    baseUrl: config.apiBaseUrl,
    serviceToken: config.serviceToken,
    timeoutMs: config.apiTimeoutMs,
  });
  return createApp({ config, logger, api });
}

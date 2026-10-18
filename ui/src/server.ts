import { composeApp } from "./composition.js";
import { loadConfig } from "./config.js";
import { createLogger } from "./logger.js";

const config = loadConfig(process.env);
const logger = createLogger(config.logLevel);
const server = composeApp(config, logger).listen(config.port, config.host, () => {
  logger.info({ host: config.host, port: config.port }, "ui server listening");
});
server.headersTimeout = 30_000;
server.requestTimeout = 120_000;

function shutdown(signal: string): void {
  logger.info({ signal }, "shutting down");
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGTERM", () => {
  shutdown("SIGTERM");
});
process.on("SIGINT", () => {
  shutdown("SIGINT");
});

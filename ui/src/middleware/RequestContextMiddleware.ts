import { randomUUID } from "node:crypto";
import type { NextFunction, Request, RequestHandler, Response } from "express";
import type { Logger } from "pino";
import { requestContext } from "../logger.js";

/** Gives every request a fresh id, binds it for logging, echoes it, and writes an access log. */
export class RequestContextMiddleware {
  constructor(private readonly logger: Logger) {}

  readonly handle: RequestHandler = (req: Request, res: Response, next: NextFunction) => {
    const requestId = randomUUID();
    const started = process.hrtime.bigint();
    res.locals.requestId = requestId;
    res.locals.currentPath = req.path;
    res.setHeader("X-Request-Id", requestId);
    requestContext.run({ requestId }, () => {
      res.on("finish", () => {
        this.logger.info(
          {
            method: req.method,
            path: req.path,
            status: res.statusCode,
            duration_ms: Number(process.hrtime.bigint() - started) / 1e6,
          },
          "request",
        );
      });
      next();
    });
  };
}

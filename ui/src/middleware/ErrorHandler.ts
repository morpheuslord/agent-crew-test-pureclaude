import type { NextFunction, Request, Response } from "express";
import type { Logger } from "pino";
import { ApiError } from "../api/errors.js";
import type { SessionMiddleware } from "./SessionMiddleware.js";

/** Maps errors to pages without revealing internal detail. */
export class ErrorHandler {
  constructor(
    private readonly logger: Logger,
    private readonly session: SessionMiddleware,
  ) {}

  readonly notFound = (_req: Request, res: Response): void => {
    res.status(404).render("error", { title: "Not found", message: "That page does not exist." });
  };

  readonly handle = (error: unknown, _req: Request, res: Response, next: NextFunction): void => {
    if (res.headersSent) {
      next(error);
      return;
    }
    if (error instanceof ApiError) {
      if (error.status === 401) {
        this.session.clear(res);
        res.redirect(303, "/login");
        return;
      }
      if (error.status === 404 || error.status === 403) {
        res.status(error.status).render("error", {
          title: error.status === 404 ? "Not found" : "Forbidden",
          message:
            error.status === 404
              ? "That page does not exist or you do not have access to it."
              : "You are not allowed to do that.",
        });
        return;
      }
      if (error.status === 409 || error.status === 413 || error.status === 422) {
        res
          .status(error.status)
          .render("error", { title: "Request rejected", message: error.message });
        return;
      }
    }
    this.logger.error({ err: error }, "request failed");
    const unavailable = error instanceof ApiError && error.status === 503;
    res.status(unavailable ? 503 : 500).render("error", {
      title: unavailable ? "Service unavailable" : "Something went wrong",
      message: "Please try again in a moment.",
    });
  };
}

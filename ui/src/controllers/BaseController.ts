import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { Request, Response } from "express";
import type { ApiClient, ApiContext } from "../api/ApiClient.js";
import { ApiError } from "../api/errors.js";
import type { BinaryDownload, User } from "../api/types.js";
import type { FlashMessages } from "../middleware/FlashMessages.js";
import { apiContext } from "../middleware/SessionMiddleware.js";

const SAFE_DISPOSITION = /^attachment;[^\r\n]*$/;

/** Helpers shared by all controllers. Controllers stay thin: parse, call the API, render. */
export abstract class BaseController {
  constructor(
    protected readonly api: ApiClient,
    protected readonly flash: FlashMessages,
  ) {}

  protected ctx(req: Request, res: Response): ApiContext {
    return apiContext(req, res);
  }

  /** The signed-in user; only call behind the requireAuth guard. */
  protected user(res: Response): User {
    const user = res.locals.user;
    if (user === undefined) {
      throw new ApiError(401, "unauthenticated", "authentication required");
    }
    return user;
  }

  /** A route parameter already validated as a UUID by the router. */
  protected param(req: Request, name: string): string {
    const value = req.params[name];
    if (typeof value !== "string") {
      throw new ApiError(404, "not_found", "not found");
    }
    return value;
  }

  /**
   * Run an action; expected API rejections (validation, conflicts, rate limits, permission,
   * unknown targets such as an email that matches no user)
   * become a flash error instead of an error page. Returns false when the action failed.
   */
  protected async attempt(res: Response, action: () => Promise<unknown>): Promise<boolean> {
    try {
      await action();
      return true;
    } catch (error) {
      if (error instanceof ApiError && [403, 404, 409, 413, 422, 429].includes(error.status)) {
        this.flash.error(res, BaseController.describe(error));
        return false;
      }
      throw error;
    }
  }

  /** Stream a file from the API to the browser as a download that is never rendered inline. */
  protected async sendDownload(
    res: Response,
    download: BinaryDownload,
    options: { contentType: string; fallbackName: string },
  ): Promise<void> {
    const disposition =
      download.contentDisposition && SAFE_DISPOSITION.test(download.contentDisposition)
        ? download.contentDisposition
        : `attachment; filename="${options.fallbackName}"`;
    res.status(200);
    res.setHeader("Content-Type", options.contentType);
    res.setHeader("Content-Disposition", disposition);
    res.setHeader("X-Content-Type-Options", "nosniff");
    if (download.contentLength && /^\d+$/.test(download.contentLength)) {
      res.setHeader("Content-Length", download.contentLength);
    }
    await pipeline(Readable.fromWeb(download.body), res);
  }

  static describe(error: ApiError): string {
    const fieldMessages = Object.entries(error.fields).map(([field, msg]) => `${field}: ${msg}`);
    return fieldMessages.length > 0
      ? `${error.message} (${fieldMessages.join(", ")})`
      : error.message;
  }
}

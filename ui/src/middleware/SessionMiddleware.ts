import type { NextFunction, Request, RequestHandler, Response } from "express";
import type { ApiClient, ApiContext } from "../api/ApiClient.js";
import { ApiError } from "../api/errors.js";
import type { LoginResult } from "../api/types.js";
import { SESSION_COOKIE, baseCookieOptions, readCookie } from "./cookies.js";

const MAX_SESSION_MS = 30 * 24 * 60 * 60 * 1000;

/** Loads the signed-in user from the API on each request and manages the session cookie. */
export class SessionMiddleware {
  constructor(
    private readonly api: ApiClient,
    private readonly secureCookies: boolean,
  ) {}

  readonly load: RequestHandler = async (req: Request, res: Response, next: NextFunction) => {
    const token = readCookie(req, SESSION_COOKIE);
    if (token === undefined || token.length > 200) {
      next();
      return;
    }
    res.locals.sessionToken = token;
    try {
      res.locals.user = await this.api.me(apiContext(req, res));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        delete res.locals.sessionToken;
        this.clear(res);
      } else {
        throw error;
      }
    }
    next();
  };

  /** Store the API session token in an HttpOnly cookie that expires with the session. */
  start(res: Response, login: LoginResult): void {
    const remaining = new Date(login.expires_at).getTime() - Date.now();
    res.cookie(SESSION_COOKIE, login.token, {
      ...baseCookieOptions(this.secureCookies),
      maxAge: Math.max(0, Math.min(remaining, MAX_SESSION_MS)),
    });
  }

  clear(res: Response): void {
    res.clearCookie(SESSION_COOKIE, baseCookieOptions(this.secureCookies));
  }
}

/** Build the API call context for this request: request id, session token, client address. */
export function apiContext(req: Request, res: Response): ApiContext {
  return { requestId: res.locals.requestId, token: res.locals.sessionToken, clientIp: req.ip };
}

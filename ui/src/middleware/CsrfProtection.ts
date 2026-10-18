import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import type { NextFunction, Request, RequestHandler, Response } from "express";
import { CSRF_COOKIE, baseCookieOptions, readCookie } from "./cookies.js";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const ONE_DAY_MS = 24 * 60 * 60 * 1000;

/**
 * HMAC-bound double-submit CSRF protection.
 *
 * Every visitor gets a random `tb_csrf` cookie. Forms carry `HMAC(secret, cookie)` in `_csrf`.
 * An attacker's page can neither read the cookie nor compute the HMAC, so it can not forge a
 * valid form. When the browser sends `Origin`, it must also match the public origin.
 */
export class CsrfProtection {
  constructor(
    private readonly secret: string,
    private readonly publicOrigin: string,
    private readonly secureCookies: boolean,
  ) {}

  /** Ensure the visitor has a CSRF cookie and expose the matching form token to templates. */
  readonly issue: RequestHandler = (req: Request, res: Response, next: NextFunction) => {
    let nonce = readCookie(req, CSRF_COOKIE);
    if (nonce === undefined || !/^[A-Za-z0-9_-]{43}$/.test(nonce)) {
      nonce = this.rotate(res);
    }
    res.locals.csrfToken = this.tokenFor(nonce);
    next();
  };

  /** Reject state-changing requests without a valid token or from a foreign origin. */
  readonly verify: RequestHandler = (req: Request, res: Response, next: NextFunction) => {
    if (SAFE_METHODS.has(req.method)) {
      next();
      return;
    }
    const origin = req.get("origin");
    const nonce = readCookie(req, CSRF_COOKIE);
    const body = req.body as Record<string, unknown> | undefined;
    const submitted = body?._csrf;
    const valid =
      (origin === undefined || origin === this.publicOrigin) &&
      nonce !== undefined &&
      typeof submitted === "string" &&
      this.matches(submitted, this.tokenFor(nonce));
    if (!valid) {
      res.status(403).render("error", {
        title: "Request blocked",
        message:
          "The form has expired or did not come from this site. Reload the page and try again.",
      });
      return;
    }
    next();
  };

  /** Issue a new nonce (after login and logout) and return it. */
  rotate(res: Response): string {
    const nonce = randomBytes(32).toString("base64url");
    res.cookie(CSRF_COOKIE, nonce, {
      ...baseCookieOptions(this.secureCookies),
      maxAge: ONE_DAY_MS,
    });
    res.locals.csrfToken = this.tokenFor(nonce);
    return nonce;
  }

  private tokenFor(nonce: string): string {
    return createHmac("sha256", this.secret).update(`csrf:${nonce}`).digest("base64url");
  }

  private matches(a: string, b: string): boolean {
    const left = Buffer.from(a);
    const right = Buffer.from(b);
    return left.length === right.length && timingSafeEqual(left, right);
  }
}

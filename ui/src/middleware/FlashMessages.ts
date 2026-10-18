import type { NextFunction, Request, RequestHandler, Response } from "express";
import { FLASH_COOKIE, baseCookieOptions, readSignedCookie } from "./cookies.js";

export interface Flash {
  type: "success" | "error";
  message: string;
}

/** One-shot messages carried across a redirect in a signed cookie. */
export class FlashMessages {
  constructor(private readonly secureCookies: boolean) {}

  readonly consume: RequestHandler = (req: Request, res: Response, next: NextFunction) => {
    const raw = readSignedCookie(req, FLASH_COOKIE);
    if (raw !== undefined) {
      res.locals.flash = FlashMessages.parse(raw);
      res.clearCookie(FLASH_COOKIE, baseCookieOptions(this.secureCookies));
    }
    next();
  };

  success(res: Response, message: string): void {
    this.set(res, { type: "success", message });
  }

  error(res: Response, message: string): void {
    this.set(res, { type: "error", message });
  }

  private set(res: Response, flash: Flash): void {
    res.cookie(FLASH_COOKIE, JSON.stringify(flash), {
      ...baseCookieOptions(this.secureCookies),
      signed: true,
      maxAge: 60_000,
    });
  }

  private static parse(raw: string): Flash | undefined {
    try {
      const value = JSON.parse(raw) as Partial<Flash>;
      if (
        (value.type === "success" || value.type === "error") &&
        typeof value.message === "string"
      ) {
        return { type: value.type, message: value.message.slice(0, 500) };
      }
    } catch {
      return undefined;
    }
    return undefined;
  }
}

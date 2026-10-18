import type { CookieOptions, Request } from "express";

export const SESSION_COOKIE = "tb_session";
export const CSRF_COOKIE = "tb_csrf";
export const FLASH_COOKIE = "tb_flash";

/** Read a plain cookie as a string, ignoring anything else cookie-parser may produce. */
export function readCookie(req: Request, name: string): string | undefined {
  const cookies = req.cookies as Record<string, unknown> | undefined;
  const value = cookies?.[name];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

/** Read a cookie signed with the UI secret; tampered values come back as undefined. */
export function readSignedCookie(req: Request, name: string): string | undefined {
  const cookies = req.signedCookies as Record<string, unknown> | undefined;
  const value = cookies?.[name];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

/** Attributes shared by every cookie the UI server sets. */
export function baseCookieOptions(secure: boolean): CookieOptions {
  return { httpOnly: true, secure, sameSite: "lax", path: "/" };
}

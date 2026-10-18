import type { NextFunction, Request, Response } from "express";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

/** Route guards: authentication, admin role, and well-formed ids in the path. */
export class Guards {
  /** Redirect anonymous visitors to the login page. */
  readonly requireAuth = (_req: Request, res: Response, next: NextFunction): void => {
    if (res.locals.user === undefined) {
      res.redirect(303, "/login");
      return;
    }
    next();
  };

  /** Only admins may continue. */
  readonly requireAdmin = (_req: Request, res: Response, next: NextFunction): void => {
    if (res.locals.user?.role !== "admin") {
      res.status(403).render("error", { title: "Forbidden", message: "Admins only." });
      return;
    }
    next();
  };

  /** Router param handler: ids that are not UUIDs never reach an API path. */
  readonly uuidParam = (_req: Request, res: Response, next: NextFunction, value: unknown): void => {
    if (!isUuid(value)) {
      res.status(404).render("error", { title: "Not found", message: "That page does not exist." });
      return;
    }
    next();
  };
}

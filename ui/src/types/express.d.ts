import type { User } from "../api/types.js";
import type { Flash } from "../middleware/FlashMessages.js";

/** Typed values the middleware puts on `res.locals` for controllers and templates. */
declare module "express-serve-static-core" {
  interface Locals {
    requestId: string;
    csrfToken: string;
    user?: User;
    sessionToken?: string;
    flash?: Flash;
    currentPath: string;
  }
}

export {};

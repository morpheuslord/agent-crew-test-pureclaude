import type { NextFunction, Request, RequestHandler, Response } from "express";
import helmet from "helmet";

/**
 * Security headers. The pages use no JavaScript at all, so scripts are disabled outright; images
 * are limited to this origin, which also blocks tracking images in user Markdown.
 */
export class SecurityHeaders {
  readonly headers: RequestHandler;

  constructor(httpsOnly: boolean) {
    this.headers = helmet({
      contentSecurityPolicy: {
        useDefaults: false,
        directives: {
          defaultSrc: ["'self'"],
          scriptSrc: ["'none'"],
          styleSrc: ["'self'"],
          imgSrc: ["'self'"],
          fontSrc: ["'self'"],
          connectSrc: ["'self'"],
          objectSrc: ["'none'"],
          baseUri: ["'none'"],
          formAction: ["'self'"],
          frameAncestors: ["'none'"],
          ...(httpsOnly ? { upgradeInsecureRequests: [] } : {}),
        },
      },
      strictTransportSecurity: httpsOnly ? { maxAge: 31_536_000, includeSubDomains: true } : false,
      referrerPolicy: { policy: "no-referrer" },
      crossOriginResourcePolicy: { policy: "same-origin" },
    });
  }

  /** Pages are per user; never let browsers or proxies cache them. */
  readonly noStore = (_req: Request, res: Response, next: NextFunction): void => {
    res.setHeader("Cache-Control", "no-store");
    next();
  };
}

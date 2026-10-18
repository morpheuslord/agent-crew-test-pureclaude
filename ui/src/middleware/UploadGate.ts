import type { NextFunction, Request, RequestHandler, Response } from "express";
import multer, { MulterError } from "multer";

const UPLOAD_PATH = /^\/tasks\/[0-9a-f-]{36}\/attachments$/i;

/**
 * Parses multipart bodies only on the attachment upload route, before CSRF verification runs, so
 * the CSRF check covers uploads too. Multipart requests anywhere else are refused, which means no
 * route can be reached with a body the CSRF middleware did not see.
 */
export class UploadGate {
  private readonly parser: RequestHandler;

  constructor(maxBytes: number) {
    this.parser = multer({
      storage: multer.memoryStorage(),
      limits: { fileSize: maxBytes, files: 1, fields: 5, fieldSize: 1024, parts: 6 },
    }).single("file");
  }

  readonly handle: RequestHandler = (req: Request, res: Response, next: NextFunction) => {
    if (!req.is("multipart/form-data")) {
      next();
      return;
    }
    if (req.method !== "POST" || !UPLOAD_PATH.test(req.path)) {
      res.status(415).render("error", {
        title: "Unsupported request",
        message: "File uploads are only accepted on a task's attachment form.",
      });
      return;
    }
    this.parser(req, res, (error: unknown) => {
      if (error instanceof MulterError) {
        res.status(error.code === "LIMIT_FILE_SIZE" ? 413 : 400).render("error", {
          title: "Upload rejected",
          message:
            error.code === "LIMIT_FILE_SIZE"
              ? "The file is larger than 10 MB."
              : "The upload could not be read.",
        });
        return;
      }
      next(error);
    });
  };
}

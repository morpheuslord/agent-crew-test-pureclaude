import type { Request, Response } from "express";
import type { ApiClient } from "../api/ApiClient.js";
import { ApiError } from "../api/errors.js";
import { forgotForm, loginForm, parseForm, registerForm, resetForm, safeValues } from "../forms.js";
import type { CsrfProtection } from "../middleware/CsrfProtection.js";
import type { FlashMessages } from "../middleware/FlashMessages.js";
import type { SessionMiddleware } from "../middleware/SessionMiddleware.js";
import { BaseController } from "./BaseController.js";

const TOKEN_PATTERN = /^[A-Za-z0-9_-]{16,200}$/;

/** Login, registration, logout and password reset pages. */
export class AuthController extends BaseController {
  constructor(
    api: ApiClient,
    flash: FlashMessages,
    private readonly session: SessionMiddleware,
    private readonly csrf: CsrfProtection,
  ) {
    super(api, flash);
  }

  readonly showLogin = (_req: Request, res: Response): void => {
    if (res.locals.user) {
      res.redirect(303, "/");
      return;
    }
    res.render("login", { values: {}, errors: {} });
  };

  readonly login = async (req: Request, res: Response): Promise<void> => {
    const form = parseForm(loginForm, req.body);
    if (!form.ok) {
      res.status(422).render("login", { values: form.values, errors: form.errors });
      return;
    }
    try {
      const result = await this.api.login(this.ctx(req, res), form.data);
      this.session.start(res, result);
      this.csrf.rotate(res);
      this.flash.success(res, `Welcome back, ${result.user.display_name}.`);
      res.redirect(303, "/");
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 429)) {
        const message =
          error.status === 401
            ? "Invalid email or password."
            : "Too many attempts. Try again later.";
        res
          .status(error.status)
          .render("login", { values: safeValues(req.body), errors: { form: message } });
        return;
      }
      throw error;
    }
  };

  readonly showRegister = (_req: Request, res: Response): void => {
    res.render("register", { values: {}, errors: {} });
  };

  readonly register = async (req: Request, res: Response): Promise<void> => {
    const form = parseForm(registerForm, req.body);
    if (!form.ok) {
      res.status(422).render("register", { values: form.values, errors: form.errors });
      return;
    }
    const { email, display_name, password } = form.data;
    try {
      await this.api.register(this.ctx(req, res), { email, display_name, password });
    } catch (error) {
      if (error instanceof ApiError && (error.isValidation || error.status === 429)) {
        res.status(error.status).render("register", {
          values: safeValues(req.body),
          errors: { form: error.message, ...error.fields },
        });
        return;
      }
      throw error;
    }
    this.flash.success(res, "Account created. You can log in now.");
    res.redirect(303, "/login");
  };

  readonly logout = async (req: Request, res: Response): Promise<void> => {
    if (res.locals.sessionToken) {
      try {
        await this.api.logout(this.ctx(req, res));
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) {
          throw error;
        }
      }
    }
    this.session.clear(res);
    this.csrf.rotate(res);
    this.flash.success(res, "You have been logged out.");
    res.redirect(303, "/login");
  };

  readonly showForgot = (_req: Request, res: Response): void => {
    res.render("forgot-password", { values: {}, errors: {} });
  };

  readonly forgot = async (req: Request, res: Response): Promise<void> => {
    const form = parseForm(forgotForm, req.body);
    if (!form.ok) {
      res.status(422).render("forgot-password", { values: form.values, errors: form.errors });
      return;
    }
    const sent = await this.attempt(res, () =>
      this.api.forgotPassword(this.ctx(req, res), form.data.email),
    );
    if (sent) {
      this.flash.success(res, "If an account exists for that address, a reset link is on its way.");
      res.redirect(303, "/login");
      return;
    }
    res.redirect(303, "/forgot-password");
  };

  readonly showReset = (req: Request, res: Response): void => {
    const token = typeof req.query.token === "string" ? req.query.token : "";
    if (!TOKEN_PATTERN.test(token)) {
      res.status(400).render("error", {
        title: "Invalid link",
        message: "This password reset link is invalid. Request a new one.",
      });
      return;
    }
    res.render("reset-password", { token, errors: {} });
  };

  readonly reset = async (req: Request, res: Response): Promise<void> => {
    const form = parseForm(resetForm, req.body);
    const token =
      typeof (req.body as Record<string, unknown>).token === "string"
        ? String((req.body as Record<string, unknown>).token)
        : "";
    if (!form.ok) {
      res.status(422).render("reset-password", { token, errors: form.errors });
      return;
    }
    try {
      await this.api.resetPassword(this.ctx(req, res), {
        token: form.data.token,
        new_password: form.data.password,
      });
    } catch (error) {
      if (error instanceof ApiError && (error.isValidation || error.status === 429)) {
        res
          .status(error.status)
          .render("reset-password", { token, errors: { form: error.message } });
        return;
      }
      throw error;
    }
    this.flash.success(res, "Your password has been changed. Log in with the new one.");
    res.redirect(303, "/login");
  };
}

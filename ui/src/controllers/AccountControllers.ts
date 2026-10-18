import type { Request, Response } from "express";
import type { ApiClient } from "../api/ApiClient.js";
import { ApiError } from "../api/errors.js";
import { adminUserForm, changePasswordForm, pageQuery, parseForm, searchQuery } from "../forms.js";
import type { FlashMessages } from "../middleware/FlashMessages.js";
import type { ActivityViewBuilder, SearchViewBuilder } from "../views/ViewModels.js";
import { BaseController } from "./BaseController.js";

/** Cross-project task search. */
export class SearchController extends BaseController {
  constructor(
    api: ApiClient,
    flash: FlashMessages,
    private readonly view: SearchViewBuilder,
  ) {
    super(api, flash);
  }

  readonly show = async (req: Request, res: Response): Promise<void> => {
    const query = searchQuery.parse(req.query);
    const searched = Object.keys(req.query).length > 0;
    const results = searched
      ? await this.api.searchTasks(this.ctx(req, res), { ...query, page_size: 20 })
      : null;
    res.render("search", this.view.build(query, results));
  };
}

/** Own profile and password change. */
export class ProfileController extends BaseController {
  readonly show = (_req: Request, res: Response): void => {
    res.render("profile", { errors: {} });
  };

  readonly changePassword = async (req: Request, res: Response): Promise<void> => {
    const form = parseForm(changePasswordForm, req.body);
    if (!form.ok) {
      res.status(422).render("profile", { errors: form.errors });
      return;
    }
    try {
      await this.api.changePassword(this.ctx(req, res), {
        current_password: form.data.current_password,
        new_password: form.data.new_password,
      });
    } catch (error) {
      if (error instanceof ApiError && (error.isValidation || error.status === 429)) {
        res
          .status(error.status)
          .render("profile", { errors: { form: error.message, ...error.fields } });
        return;
      }
      throw error;
    }
    this.flash.success(res, "Password changed. Other sessions have been signed out.");
    res.redirect(303, "/profile");
  };
}

/** User administration and the global activity feed. */
export class AdminController extends BaseController {
  constructor(
    api: ApiClient,
    flash: FlashMessages,
    private readonly activityView: ActivityViewBuilder,
  ) {
    super(api, flash);
  }

  readonly users = async (req: Request, res: Response): Promise<void> => {
    const { page, q } = pageQuery.parse(req.query);
    const users = await this.api.listUsers(this.ctx(req, res), { q, page });
    res.render("admin-users", {
      users,
      q: q ?? "",
      lastPage: Math.max(1, Math.ceil(users.total / users.page_size)),
    });
  };

  readonly updateUser = async (req: Request, res: Response): Promise<void> => {
    const userId = this.param(req, "userId");
    const form = parseForm(adminUserForm, req.body);
    if (!form.ok || (form.data.role === undefined && form.data.is_active === undefined)) {
      this.flash.error(res, "Nothing to change.");
    } else {
      const changes = form.data;
      if (await this.attempt(res, () => this.api.updateUser(this.ctx(req, res), userId, changes))) {
        this.flash.success(res, "User updated.");
      }
    }
    res.redirect(303, "/admin/users");
  };

  readonly activity = async (req: Request, res: Response): Promise<void> => {
    const { page } = pageQuery.parse(req.query);
    const feed = await this.api.globalActivity(this.ctx(req, res), page);
    res.render("activity", {
      heading: "All activity",
      backHref: "/admin/users",
      baseHref: "/admin/activity",
      feed: this.activityView.build(feed),
    });
  };
}

/** Liveness and readiness probes for the load balancer. */
export class HealthController {
  constructor(private readonly api: ApiClient) {}

  readonly healthz = (_req: Request, res: Response): void => {
    res.json({ status: "ok" });
  };

  readonly readyz = async (_req: Request, res: Response): Promise<void> => {
    const apiReady = await this.api.ready(res.locals.requestId);
    res.status(apiReady ? 200 : 503).json({
      status: apiReady ? "ready" : "not_ready",
      checks: { api: apiReady ? "ok" : "unavailable" },
    });
  };
}

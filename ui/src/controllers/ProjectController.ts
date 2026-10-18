import type { Request, Response } from "express";
import type { ApiClient } from "../api/ApiClient.js";
import type { Page, Task, TaskStatus } from "../api/types.js";
import { TASK_STATUSES } from "../api/types.js";
import { pageQuery, parseForm, projectForm, taskForm } from "../forms.js";
import type { FlashMessages } from "../middleware/FlashMessages.js";
import type { ActivityViewBuilder, BoardViewBuilder } from "../views/ViewModels.js";
import { BaseController } from "./BaseController.js";

/** Project board, settings, task creation, CSV export and activity feed. */
export class ProjectController extends BaseController {
  constructor(
    api: ApiClient,
    flash: FlashMessages,
    private readonly board: BoardViewBuilder,
    private readonly activityView: ActivityViewBuilder,
  ) {
    super(api, flash);
  }

  readonly show = async (req: Request, res: Response): Promise<void> => {
    const ctx = this.ctx(req, res);
    const projectId = this.param(req, "projectId");
    const project = await this.api.getProject(ctx, projectId);
    const pages = await Promise.all(
      TASK_STATUSES.map((status) =>
        this.api.listTasks(ctx, projectId, {
          status,
          sort: "priority",
          order: "desc",
          page_size: 100,
        }),
      ),
    );
    const byStatus = Object.fromEntries(
      TASK_STATUSES.map((status, index) => [status, pages[index]]),
    ) as Record<TaskStatus, Page<Task>>;
    res.render("project", this.board.build(project, byStatus));
  };

  readonly createTask = async (req: Request, res: Response): Promise<void> => {
    const projectId = this.param(req, "projectId");
    const form = parseForm(taskForm, req.body);
    if (!form.ok) {
      this.flash.error(
        res,
        `Task not created: ${Object.entries(form.errors)
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ")}`,
      );
      res.redirect(303, `/projects/${projectId}`);
      return;
    }
    let taskId = "";
    const ok = await this.attempt(res, async () => {
      taskId = (await this.api.createTask(this.ctx(req, res), projectId, form.data)).id;
    });
    if (ok) {
      this.flash.success(res, "Task created.");
      res.redirect(303, `/tasks/${taskId}`);
      return;
    }
    res.redirect(303, `/projects/${projectId}`);
  };

  readonly updateSettings = async (req: Request, res: Response): Promise<void> => {
    const projectId = this.param(req, "projectId");
    const form = parseForm(projectForm, req.body);
    if (!form.ok) {
      this.flash.error(res, Object.values(form.errors).join(" "));
    } else if (
      await this.attempt(res, () =>
        this.api.updateProject(this.ctx(req, res), projectId, form.data),
      )
    ) {
      this.flash.success(res, "Project settings saved.");
    }
    res.redirect(303, `/projects/${projectId}`);
  };

  readonly archive = async (req: Request, res: Response): Promise<void> => {
    const projectId = this.param(req, "projectId");
    if (await this.attempt(res, () => this.api.archiveProject(this.ctx(req, res), projectId))) {
      this.flash.success(res, "Project archived. It is now read-only.");
    }
    res.redirect(303, `/projects/${projectId}`);
  };

  readonly exportCsv = async (req: Request, res: Response): Promise<void> => {
    const projectId = this.param(req, "projectId");
    const download = await this.api.exportCsv(this.ctx(req, res), projectId);
    await this.sendDownload(res, download, {
      contentType: "text/csv; charset=utf-8",
      fallbackName: "tasks.csv",
    });
  };

  readonly activity = async (req: Request, res: Response): Promise<void> => {
    const ctx = this.ctx(req, res);
    const projectId = this.param(req, "projectId");
    const { page } = pageQuery.parse(req.query);
    const [project, feed] = await Promise.all([
      this.api.getProject(ctx, projectId),
      this.api.projectActivity(ctx, projectId, page),
    ]);
    res.render("activity", {
      heading: `Activity: ${project.name}`,
      backHref: `/projects/${project.id}`,
      baseHref: `/projects/${project.id}/activity`,
      feed: this.activityView.build(feed),
    });
  };
}

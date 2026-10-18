import type { Request, Response } from "express";
import type { ApiClient } from "../api/ApiClient.js";
import {
  commentDeleteForm,
  commentEditForm,
  commentForm,
  parseForm,
  statusForm,
  taskForm,
} from "../forms.js";
import type { FlashMessages } from "../middleware/FlashMessages.js";
import type { TaskViewBuilder } from "../views/ViewModels.js";
import { BaseController } from "./BaseController.js";

/** Task detail, edits, comments and attachments. */
export class TaskController extends BaseController {
  constructor(
    api: ApiClient,
    flash: FlashMessages,
    private readonly view: TaskViewBuilder,
  ) {
    super(api, flash);
  }

  readonly show = async (req: Request, res: Response): Promise<void> => {
    const ctx = this.ctx(req, res);
    const taskId = this.param(req, "taskId");
    const task = await this.api.getTask(ctx, taskId);
    const [project, comments, attachments] = await Promise.all([
      this.api.getProject(ctx, task.project_id),
      this.api.listComments(ctx, taskId),
      this.api.listAttachments(ctx, taskId),
    ]);
    res.render("task", this.view.build(task, project, comments, attachments, this.user(res)));
  };

  readonly update = async (req: Request, res: Response): Promise<void> => {
    const taskId = this.param(req, "taskId");
    const form = parseForm(taskForm, req.body);
    if (!form.ok) {
      this.flash.error(
        res,
        `Not saved: ${Object.entries(form.errors)
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ")}`,
      );
    } else if (
      await this.attempt(res, () => this.api.updateTask(this.ctx(req, res), taskId, form.data))
    ) {
      this.flash.success(res, "Task saved.");
    }
    res.redirect(303, `/tasks/${taskId}`);
  };

  readonly setStatus = async (req: Request, res: Response): Promise<void> => {
    const taskId = this.param(req, "taskId");
    const form = parseForm(statusForm, req.body);
    if (!form.ok) {
      this.flash.error(res, "Choose a valid status.");
    } else if (
      await this.attempt(res, () =>
        this.api.updateTask(this.ctx(req, res), taskId, { status: form.data.status }),
      )
    ) {
      this.flash.success(res, "Status updated.");
    }
    res.redirect(303, `/tasks/${taskId}`);
  };

  readonly remove = async (req: Request, res: Response): Promise<void> => {
    const ctx = this.ctx(req, res);
    const taskId = this.param(req, "taskId");
    const task = await this.api.getTask(ctx, taskId);
    if (await this.attempt(res, () => this.api.deleteTask(ctx, taskId))) {
      this.flash.success(res, "Task deleted.");
      res.redirect(303, `/projects/${task.project_id}`);
      return;
    }
    res.redirect(303, `/tasks/${taskId}`);
  };

  readonly addComment = async (req: Request, res: Response): Promise<void> => {
    const taskId = this.param(req, "taskId");
    const form = parseForm(commentForm, req.body);
    if (!form.ok) {
      this.flash.error(res, form.errors.body ?? "Invalid comment.");
    } else if (
      await this.attempt(res, () => this.api.addComment(this.ctx(req, res), taskId, form.data.body))
    ) {
      this.flash.success(res, "Comment added.");
    }
    res.redirect(303, `/tasks/${taskId}`);
  };

  readonly editComment = async (req: Request, res: Response): Promise<void> => {
    const commentId = this.param(req, "commentId");
    const form = parseForm(commentEditForm, req.body);
    if (!form.ok) {
      this.flash.error(res, form.errors.body ?? "Invalid comment.");
      res.redirect(303, "/");
      return;
    }
    if (
      await this.attempt(res, () =>
        this.api.updateComment(this.ctx(req, res), commentId, form.data.body),
      )
    ) {
      this.flash.success(res, "Comment updated.");
    }
    res.redirect(303, `/tasks/${form.data.task_id}`);
  };

  readonly deleteComment = async (req: Request, res: Response): Promise<void> => {
    const commentId = this.param(req, "commentId");
    const form = parseForm(commentDeleteForm, req.body);
    if (await this.attempt(res, () => this.api.deleteComment(this.ctx(req, res), commentId))) {
      this.flash.success(res, "Comment deleted.");
    }
    res.redirect(303, form.ok ? `/tasks/${form.data.task_id}` : "/");
  };

  readonly upload = async (req: Request, res: Response): Promise<void> => {
    const taskId = this.param(req, "taskId");
    const file = req.file;
    if (file === undefined) {
      this.flash.error(res, "Choose a file to upload.");
    } else if (
      await this.attempt(res, () =>
        this.api.uploadAttachment(this.ctx(req, res), taskId, {
          filename: file.originalname,
          contentType: file.mimetype || "application/octet-stream",
          data: file.buffer,
        }),
      )
    ) {
      this.flash.success(res, "File attached.");
    }
    res.redirect(303, `/tasks/${taskId}`);
  };

  readonly download = async (req: Request, res: Response): Promise<void> => {
    const attachmentId = this.param(req, "attachmentId");
    const download = await this.api.downloadAttachment(this.ctx(req, res), attachmentId);
    await this.sendDownload(res, download, {
      contentType: "application/octet-stream",
      fallbackName: "download",
    });
  };
}

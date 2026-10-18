import { randomUUID } from "node:crypto";
import type { ApiClient, ApiContext, ProjectChanges } from "../src/api/ApiClient.js";
import { ApiError } from "../src/api/errors.js";
import type {
  Activity,
  Attachment,
  BinaryDownload,
  Comment,
  Member,
  Page,
  Project,
  ProjectDetail,
  Task,
  TaskInput,
  TaskQuery,
  TaskSearchItem,
  Team,
  TeamDetail,
  UploadFile,
} from "../src/api/types.js";
import { FakeAccountsApi } from "./FakeAccountsApi.js";
import { NOW, page, stream } from "./FakeApiBase.js";

/** A small in-memory stand-in for the API with the same error semantics. */
export class FakeApi extends FakeAccountsApi implements ApiClient {
  listTeams(ctx: ApiContext): Promise<Team[]> {
    this.record("listTeams", ctx);
    const user = this.caller(ctx);
    return Promise.resolve(
      [...this.teams.values()].filter((t) => t.members.some((m) => m.user_id === user.id)),
    );
  }

  createTeam(ctx: ApiContext, name: string): Promise<Team> {
    this.record("createTeam", ctx, name);
    const user = this.caller(ctx);
    const team: TeamDetail = {
      id: randomUUID(),
      name,
      owner_id: user.id,
      created_at: NOW,
      can_manage: true,
      members: [
        {
          user_id: user.id,
          email: user.email,
          display_name: user.display_name,
          is_owner: true,
          added_at: NOW,
        },
      ],
    };
    this.teams.set(team.id, team);
    return Promise.resolve(team);
  }

  getTeam(ctx: ApiContext, teamId: string) {
    this.record("getTeam", ctx, teamId);
    return Promise.resolve(this.team(ctx, teamId));
  }

  addMember(ctx: ApiContext, teamId: string, email: string): Promise<Member> {
    this.record("addMember", ctx, teamId, email);
    const team = this.team(ctx, teamId);
    const user = [...this.users.values()].find((u) => u.email === email);
    if (!user) {
      return Promise.reject(
        new ApiError(404, "not_found", "no active user has that email address"),
      );
    }
    const member = {
      user_id: user.id,
      email,
      display_name: user.display_name,
      is_owner: false,
      added_at: NOW,
    };
    this.teams.get(team.id)?.members.push(member);
    return Promise.resolve(member);
  }

  removeMember(ctx: ApiContext, teamId: string, userId: string) {
    this.record("removeMember", ctx, teamId, userId);
    const team = this.teams.get(this.team(ctx, teamId).id);
    if (team) {
      team.members = team.members.filter((m) => m.user_id !== userId);
    }
    return Promise.resolve();
  }

  listTeamProjects(ctx: ApiContext, teamId: string): Promise<Project[]> {
    this.record("listTeamProjects", ctx, teamId);
    this.team(ctx, teamId);
    return Promise.resolve([...this.projects.values()].filter((p) => p.team_id === teamId));
  }

  createProject(
    ctx: ApiContext,
    teamId: string,
    body: { name: string; webhook_url: string | null },
  ) {
    this.record("createProject", ctx, teamId, body);
    const team = this.team(ctx, teamId);
    if (body.webhook_url?.startsWith("http://")) {
      return Promise.reject(
        new ApiError(422, "validation_failed", "webhook URL must use https", {
          webhook_url: "webhook URL must use https",
        }),
      );
    }
    const project: ProjectDetail = {
      id: randomUUID(),
      team_id: team.id,
      team_name: team.name,
      name: body.name,
      archived: false,
      created_at: NOW,
      updated_at: NOW,
      can_manage: true,
      members: team.members,
      webhook_url: body.webhook_url,
      webhook_secret: body.webhook_url ? "secret-value" : null,
    };
    this.projects.set(project.id, project);
    return Promise.resolve(project);
  }

  listMyProjects(ctx: ApiContext): Promise<Project[]> {
    this.record("listMyProjects", ctx);
    const user = this.caller(ctx);
    const teamIds = new Set(
      [...this.teams.values()]
        .filter((t) => t.members.some((m) => m.user_id === user.id))
        .map((t) => t.id),
    );
    return Promise.resolve([...this.projects.values()].filter((p) => teamIds.has(p.team_id)));
  }

  getProject(ctx: ApiContext, projectId: string) {
    this.record("getProject", ctx, projectId);
    return Promise.resolve(this.project(ctx, projectId));
  }

  updateProject(ctx: ApiContext, projectId: string, body: ProjectChanges) {
    this.record("updateProject", ctx, projectId, body);
    const project = this.projects.get(this.project(ctx, projectId).id);
    if (project) {
      Object.assign(project, body);
      project.webhook_secret = project.webhook_url
        ? (project.webhook_secret ?? "secret-value")
        : null;
    }
    return Promise.resolve(this.project(ctx, projectId));
  }

  archiveProject(ctx: ApiContext, projectId: string) {
    this.record("archiveProject", ctx, projectId);
    const project = this.projects.get(this.project(ctx, projectId).id);
    if (project) {
      project.archived = true;
    }
    return Promise.resolve(this.project(ctx, projectId));
  }

  listTasks(ctx: ApiContext, projectId: string, query: TaskQuery): Promise<Page<Task>> {
    this.record("listTasks", ctx, projectId, query);
    this.project(ctx, projectId);
    const items = [...this.tasks.values()].filter(
      (t) => t.project_id === projectId && (!query.status || t.status === query.status),
    );
    return Promise.resolve(page(items, query.page ?? 1, query.page_size ?? 20));
  }

  createTask(ctx: ApiContext, projectId: string, body: TaskInput): Promise<Task> {
    this.record("createTask", ctx, projectId, body);
    const project = this.project(ctx, projectId);
    if (project.archived) {
      return Promise.reject(new ApiError(409, "conflict", "the project is archived and read-only"));
    }
    const user = this.caller(ctx);
    const task: Task = {
      id: randomUUID(),
      project_id: projectId,
      ...body,
      assignee_name: null,
      created_by: user.id,
      created_at: NOW,
      updated_at: NOW,
    };
    this.tasks.set(task.id, task);
    return Promise.resolve(task);
  }

  exportCsv(ctx: ApiContext, projectId: string): Promise<BinaryDownload> {
    this.record("exportCsv", ctx, projectId);
    this.project(ctx, projectId);
    return Promise.resolve({
      body: stream(Buffer.from('"id","title"\r\n')),
      contentType: "text/csv; charset=utf-8",
      contentDisposition: 'attachment; filename="Roadmap-tasks.csv"',
      contentLength: "14",
    });
  }

  projectActivity(ctx: ApiContext, projectId: string, pageNumber: number): Promise<Page<Activity>> {
    this.record("projectActivity", ctx, projectId, pageNumber);
    const project = this.project(ctx, projectId);
    return Promise.resolve(
      page([
        {
          id: randomUUID(),
          actor_id: null,
          actor_name: "Olive",
          event_type: "task.created",
          team_id: project.team_id,
          project_id: projectId,
          task_id: null,
          details: { title: "<b>Ship</b>" },
          created_at: NOW,
        },
      ]),
    );
  }

  getTask(ctx: ApiContext, taskId: string) {
    this.record("getTask", ctx, taskId);
    return Promise.resolve(this.task(ctx, taskId));
  }

  updateTask(ctx: ApiContext, taskId: string, body: Partial<TaskInput>) {
    this.record("updateTask", ctx, taskId, body);
    const task = this.task(ctx, taskId);
    Object.assign(task, body);
    return Promise.resolve(task);
  }

  deleteTask(ctx: ApiContext, taskId: string) {
    this.record("deleteTask", ctx, taskId);
    this.task(ctx, taskId);
    this.tasks.delete(taskId);
    return Promise.resolve();
  }

  listComments(ctx: ApiContext, taskId: string) {
    this.record("listComments", ctx, taskId);
    this.task(ctx, taskId);
    return Promise.resolve([...this.comments.values()].filter((c) => c.task_id === taskId));
  }

  addComment(ctx: ApiContext, taskId: string, body: string): Promise<Comment> {
    this.record("addComment", ctx, taskId, body);
    this.task(ctx, taskId);
    const user = this.caller(ctx);
    const comment = {
      id: randomUUID(),
      task_id: taskId,
      author_id: user.id,
      author_name: user.display_name,
      body,
      created_at: NOW,
      updated_at: NOW,
    };
    this.comments.set(comment.id, comment);
    return Promise.resolve(comment);
  }

  updateComment(ctx: ApiContext, commentId: string, body: string) {
    this.record("updateComment", ctx, commentId, body);
    const comment = this.comments.get(commentId);
    if (!comment) {
      return Promise.reject(new ApiError(404, "not_found", "comment not found"));
    }
    if (comment.author_id !== this.caller(ctx).id) {
      return Promise.reject(
        new ApiError(403, "forbidden", "only the author can change this comment"),
      );
    }
    comment.body = body;
    comment.updated_at = "2026-10-18T10:00:00.000Z";
    return Promise.resolve(comment);
  }

  deleteComment(ctx: ApiContext, commentId: string) {
    this.record("deleteComment", ctx, commentId);
    this.caller(ctx);
    this.comments.delete(commentId);
    return Promise.resolve();
  }

  listAttachments(ctx: ApiContext, taskId: string): Promise<Attachment[]> {
    this.record("listAttachments", ctx, taskId);
    this.task(ctx, taskId);
    return Promise.resolve(
      [...this.attachments.values()]
        .filter((a) => a.task_id === taskId)
        .map((a) => FakeApi.publicAttachment(a)),
    );
  }

  uploadAttachment(ctx: ApiContext, taskId: string, file: UploadFile): Promise<Attachment> {
    this.record("uploadAttachment", ctx, taskId, file.filename);
    this.task(ctx, taskId);
    const user = this.caller(ctx);
    const attachment = {
      id: randomUUID(),
      task_id: taskId,
      uploader_id: user.id,
      uploader_name: user.display_name,
      filename: file.filename,
      content_type: file.contentType,
      size_bytes: file.data.length,
      created_at: NOW,
      data: file.data,
    };
    this.attachments.set(attachment.id, attachment);
    return Promise.resolve(attachment);
  }

  downloadAttachment(ctx: ApiContext, attachmentId: string): Promise<BinaryDownload> {
    this.record("downloadAttachment", ctx, attachmentId);
    const attachment = this.attachments.get(attachmentId);
    if (!attachment) {
      return Promise.reject(new ApiError(404, "not_found", "attachment not found"));
    }
    this.task(ctx, attachment.task_id);
    return Promise.resolve({
      body: stream(attachment.data),
      contentType: "application/octet-stream",
      contentDisposition: `attachment; filename="${attachment.filename}"`,
      contentLength: String(attachment.data.length),
    });
  }

  searchTasks(ctx: ApiContext, query: TaskQuery): Promise<Page<TaskSearchItem>> {
    this.record("searchTasks", ctx, query);
    this.caller(ctx);
    const items = [...this.tasks.values()]
      .filter(
        (t) =>
          (!query.q || t.title.includes(query.q)) &&
          (!query.assignee_id || t.assignee_id === query.assignee_id),
      )
      .map((t) => ({ ...t, project_name: this.projects.get(t.project_id)?.name ?? "" }));
    return Promise.resolve(page(items, query.page ?? 1, query.page_size ?? 20));
  }
}

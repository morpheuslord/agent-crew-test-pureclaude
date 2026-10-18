import { randomUUID } from "node:crypto";
import type { ApiContext } from "../src/api/ApiClient.js";
import { ApiError } from "../src/api/errors.js";
import type {
  Attachment,
  Comment,
  Page,
  ProjectDetail,
  Task,
  TeamDetail,
  User,
} from "../src/api/types.js";

export const NOW = "2026-10-18T09:00:00.000Z";

export function page<T>(items: T[], pageNumber = 1, size = 20): Page<T> {
  const start = (pageNumber - 1) * size;
  return {
    items: items.slice(start, start + size),
    page: pageNumber,
    page_size: size,
    total: items.length,
  };
}

export function stream(data: Uint8Array): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(data);
      controller.close();
    },
  });
}

/** Shared state, error semantics and access checks of the fake API. */
export abstract class FakeApiBase {
  readonly users = new Map<string, User & { password: string }>();

  readonly sessions = new Map<string, string>();

  readonly teams = new Map<string, TeamDetail>();

  readonly projects = new Map<string, ProjectDetail>();

  readonly tasks = new Map<string, Task>();

  readonly comments = new Map<string, Comment>();

  readonly attachments = new Map<string, Attachment & { data: Buffer }>();

  readonly calls: { method: string; ctx: ApiContext; args: unknown[] }[] = [];

  readonly outbox: string[] = [];
  failWith: ApiError | null = null;
  isReady = true;
  addUser(email: string, password: string, role: "admin" | "member" = "member"): User {
    const user = {
      id: randomUUID(),
      email,
      display_name: email.split("@")[0] ?? email,
      role,
      is_active: true,
      created_at: NOW,
      password,
    };
    this.users.set(user.id, user);
    return this.publicUser(user);
  }

  protected record(method: string, ctx: ApiContext, ...args: unknown[]): void {
    this.calls.push({ method, ctx, args });
    if (this.failWith) {
      const error = this.failWith;
      this.failWith = null;
      throw error;
    }
  }

  protected static publicAttachment(a: Attachment & { data: Buffer }): Attachment {
    return {
      id: a.id,
      task_id: a.task_id,
      uploader_id: a.uploader_id,
      uploader_name: a.uploader_name,
      filename: a.filename,
      content_type: a.content_type,
      size_bytes: a.size_bytes,
      created_at: a.created_at,
    };
  }

  protected publicUser(user: User & { password?: string }): User {
    return {
      id: user.id,
      email: user.email,
      display_name: user.display_name,
      role: user.role,
      is_active: user.is_active,
      created_at: user.created_at,
    };
  }

  protected caller(ctx: ApiContext): User & { password: string } {
    const userId = ctx.token ? this.sessions.get(ctx.token) : undefined;
    const user = userId ? this.users.get(userId) : undefined;
    if (!user?.is_active) {
      throw new ApiError(401, "unauthenticated", "session is invalid or has expired");
    }
    return user;
  }

  protected team(ctx: ApiContext, teamId: string): TeamDetail {
    const user = this.caller(ctx);
    const team = this.teams.get(teamId);
    if (!team || (!team.members.some((m) => m.user_id === user.id) && user.role !== "admin")) {
      throw new ApiError(404, "not_found", "team not found");
    }
    return { ...team, can_manage: team.owner_id === user.id || user.role === "admin" };
  }

  protected project(ctx: ApiContext, projectId: string): ProjectDetail {
    const project = this.projects.get(projectId);
    if (!project) {
      throw new ApiError(404, "not_found", "project not found");
    }
    const team = this.team(ctx, project.team_id);
    return {
      ...project,
      can_manage: team.can_manage,
      members: team.members,
      webhook_secret: team.can_manage ? project.webhook_secret : null,
    };
  }

  protected task(ctx: ApiContext, taskId: string): Task {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new ApiError(404, "not_found", "task not found");
    }
    this.project(ctx, task.project_id);
    return task;
  }
}

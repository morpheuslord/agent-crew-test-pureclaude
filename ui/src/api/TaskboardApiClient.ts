import type { ApiClient, ApiContext, ProjectChanges, UserChanges } from "./ApiClient.js";
import { ApiError, apiErrorFrom } from "./errors.js";
import type {
  Activity,
  Attachment,
  BinaryDownload,
  Comment,
  LoginResult,
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
  User,
} from "./types.js";

type Method = "GET" | "POST" | "PATCH" | "DELETE";
type QueryValue = string | number | undefined;

interface RequestOptions {
  json?: unknown;
  form?: FormData;
  query?: Record<string, QueryValue>;
}

export interface ApiClientOptions {
  baseUrl: string;
  serviceToken: string;
  timeoutMs: number;
  fetchImpl?: typeof fetch;
}

/** Encode one path segment; ids are validated upstream, this is defence in depth. */
function seg(value: string): string {
  return encodeURIComponent(value);
}

/** The only code in the UI server that talks to the API. */
export class TaskboardApiClient implements ApiClient {
  private readonly fetchImpl: typeof fetch;

  constructor(private readonly options: ApiClientOptions) {
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  register(ctx: ApiContext, body: { email: string; display_name: string; password: string }) {
    return this.json<User>(ctx, "POST", "/auth/register", { json: body });
  }

  login(ctx: ApiContext, body: { email: string; password: string }) {
    return this.json<LoginResult>(ctx, "POST", "/auth/login", { json: body });
  }

  logout(ctx: ApiContext) {
    return this.empty(ctx, "POST", "/auth/logout");
  }

  me(ctx: ApiContext) {
    return this.json<User>(ctx, "GET", "/auth/me");
  }

  changePassword(ctx: ApiContext, body: { current_password: string; new_password: string }) {
    return this.empty(ctx, "POST", "/auth/password/change", { json: body });
  }

  forgotPassword(ctx: ApiContext, email: string) {
    return this.empty(ctx, "POST", "/auth/password/forgot", { json: { email } });
  }

  resetPassword(ctx: ApiContext, body: { token: string; new_password: string }) {
    return this.empty(ctx, "POST", "/auth/password/reset", { json: body });
  }

  listTeams(ctx: ApiContext) {
    return this.json<Team[]>(ctx, "GET", "/teams");
  }

  createTeam(ctx: ApiContext, name: string) {
    return this.json<Team>(ctx, "POST", "/teams", { json: { name } });
  }

  getTeam(ctx: ApiContext, teamId: string) {
    return this.json<TeamDetail>(ctx, "GET", `/teams/${seg(teamId)}`);
  }

  addMember(ctx: ApiContext, teamId: string, email: string) {
    return this.json<Member>(ctx, "POST", `/teams/${seg(teamId)}/members`, { json: { email } });
  }

  removeMember(ctx: ApiContext, teamId: string, userId: string) {
    return this.empty(ctx, "DELETE", `/teams/${seg(teamId)}/members/${seg(userId)}`);
  }

  listTeamProjects(ctx: ApiContext, teamId: string) {
    return this.json<Project[]>(ctx, "GET", `/teams/${seg(teamId)}/projects`);
  }

  createProject(
    ctx: ApiContext,
    teamId: string,
    body: { name: string; webhook_url: string | null },
  ) {
    return this.json<ProjectDetail>(ctx, "POST", `/teams/${seg(teamId)}/projects`, { json: body });
  }

  listMyProjects(ctx: ApiContext) {
    return this.json<Project[]>(ctx, "GET", "/projects");
  }

  getProject(ctx: ApiContext, projectId: string) {
    return this.json<ProjectDetail>(ctx, "GET", `/projects/${seg(projectId)}`);
  }

  updateProject(ctx: ApiContext, projectId: string, body: ProjectChanges) {
    return this.json<ProjectDetail>(ctx, "PATCH", `/projects/${seg(projectId)}`, { json: body });
  }

  archiveProject(ctx: ApiContext, projectId: string) {
    return this.json<ProjectDetail>(ctx, "POST", `/projects/${seg(projectId)}/archive`);
  }

  listTasks(ctx: ApiContext, projectId: string, query: TaskQuery) {
    return this.json<Page<Task>>(ctx, "GET", `/projects/${seg(projectId)}/tasks`, {
      query: { ...query },
    });
  }

  createTask(ctx: ApiContext, projectId: string, body: TaskInput) {
    return this.json<Task>(ctx, "POST", `/projects/${seg(projectId)}/tasks`, { json: body });
  }

  exportCsv(ctx: ApiContext, projectId: string) {
    return this.binary(ctx, `/projects/${seg(projectId)}/export.csv`);
  }

  projectActivity(ctx: ApiContext, projectId: string, page: number) {
    return this.json<Page<Activity>>(ctx, "GET", `/projects/${seg(projectId)}/activity`, {
      query: { page, page_size: 50 },
    });
  }

  getTask(ctx: ApiContext, taskId: string) {
    return this.json<Task>(ctx, "GET", `/tasks/${seg(taskId)}`);
  }

  updateTask(ctx: ApiContext, taskId: string, body: Partial<TaskInput>) {
    return this.json<Task>(ctx, "PATCH", `/tasks/${seg(taskId)}`, { json: body });
  }

  deleteTask(ctx: ApiContext, taskId: string) {
    return this.empty(ctx, "DELETE", `/tasks/${seg(taskId)}`);
  }

  listComments(ctx: ApiContext, taskId: string) {
    return this.json<Comment[]>(ctx, "GET", `/tasks/${seg(taskId)}/comments`);
  }

  addComment(ctx: ApiContext, taskId: string, body: string) {
    return this.json<Comment>(ctx, "POST", `/tasks/${seg(taskId)}/comments`, { json: { body } });
  }

  updateComment(ctx: ApiContext, commentId: string, body: string) {
    return this.json<Comment>(ctx, "PATCH", `/comments/${seg(commentId)}`, { json: { body } });
  }

  deleteComment(ctx: ApiContext, commentId: string) {
    return this.empty(ctx, "DELETE", `/comments/${seg(commentId)}`);
  }

  listAttachments(ctx: ApiContext, taskId: string) {
    return this.json<Attachment[]>(ctx, "GET", `/tasks/${seg(taskId)}/attachments`);
  }

  uploadAttachment(ctx: ApiContext, taskId: string, file: UploadFile) {
    const form = new FormData();
    form.append("file", new Blob([file.data], { type: file.contentType }), file.filename);
    return this.json<Attachment>(ctx, "POST", `/tasks/${seg(taskId)}/attachments`, { form });
  }

  downloadAttachment(ctx: ApiContext, attachmentId: string) {
    return this.binary(ctx, `/attachments/${seg(attachmentId)}/download`);
  }

  searchTasks(ctx: ApiContext, query: TaskQuery) {
    return this.json<Page<TaskSearchItem>>(ctx, "GET", "/search/tasks", { query: { ...query } });
  }

  listUsers(ctx: ApiContext, query: { q?: string | undefined; page: number }) {
    return this.json<Page<User>>(ctx, "GET", "/admin/users", {
      query: { q: query.q, page: query.page, page_size: 50 },
    });
  }

  updateUser(ctx: ApiContext, userId: string, body: UserChanges) {
    return this.json<User>(ctx, "PATCH", `/admin/users/${seg(userId)}`, { json: body });
  }

  globalActivity(ctx: ApiContext, page: number) {
    return this.json<Page<Activity>>(ctx, "GET", "/admin/activity", {
      query: { page, page_size: 50 },
    });
  }

  async ready(requestId: string): Promise<boolean> {
    try {
      const response = await this.fetchImpl(`${this.options.baseUrl}/readyz`, {
        headers: { "X-Request-Id": requestId },
        signal: AbortSignal.timeout(this.options.timeoutMs),
      });
      await response.body?.cancel();
      return response.ok;
    } catch {
      return false;
    }
  }

  private async json<T>(
    ctx: ApiContext,
    method: Method,
    path: string,
    options: RequestOptions = {},
  ): Promise<T> {
    const response = await this.send(ctx, method, path, options);
    return (await response.json()) as T;
  }

  private async empty(
    ctx: ApiContext,
    method: Method,
    path: string,
    options: RequestOptions = {},
  ): Promise<void> {
    const response = await this.send(ctx, method, path, options);
    await response.body?.cancel();
  }

  private async binary(ctx: ApiContext, path: string): Promise<BinaryDownload> {
    const response = await this.send(ctx, "GET", path, {});
    if (response.body === null) {
      throw new ApiError(502, "bad_gateway", "the API returned no content");
    }
    return {
      body: response.body,
      contentType: response.headers.get("content-type") ?? "application/octet-stream",
      contentDisposition: response.headers.get("content-disposition"),
      contentLength: response.headers.get("content-length"),
    };
  }

  private async send(
    ctx: ApiContext,
    method: Method,
    path: string,
    options: RequestOptions,
  ): Promise<Response> {
    const url = new URL(`${this.options.baseUrl}/api/v1${path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
    const headers = new Headers({
      Accept: "application/json",
      "X-Service-Token": this.options.serviceToken,
      "X-Request-Id": ctx.requestId,
    });
    if (ctx.token) {
      headers.set("Authorization", `Bearer ${ctx.token}`);
    }
    if (ctx.clientIp) {
      headers.set("X-Client-Ip", ctx.clientIp);
    }
    let body: string | FormData | undefined;
    if (options.form) {
      body = options.form;
    } else if (options.json !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(options.json);
    }
    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method,
        headers,
        body,
        redirect: "error",
        signal: AbortSignal.timeout(this.options.timeoutMs),
      });
    } catch {
      throw new ApiError(503, "api_unavailable", "the service is temporarily unavailable");
    }
    if (!response.ok) {
      const parsed: unknown = await response.json().catch(() => null);
      throw apiErrorFrom(response.status, parsed);
    }
    return response;
  }
}

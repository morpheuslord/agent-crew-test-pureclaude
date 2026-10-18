import { describe, expect, it } from "vitest";
import { ApiError, apiErrorFrom } from "../src/api/errors.js";
import { TaskboardApiClient } from "../src/api/TaskboardApiClient.js";

interface Captured {
  url: string;
  init: RequestInit;
}

function client(respond: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const captured: Captured[] = [];
  const fetchImpl = ((input: string | URL | Request, init?: RequestInit) => {
    const url =
      input instanceof URL ? input.toString() : typeof input === "string" ? input : input.url;
    captured.push({ url, init: init ?? {} });
    return Promise.resolve(respond(url, init ?? {}));
  }) as typeof fetch;
  const api = new TaskboardApiClient({
    baseUrl: "http://api.test:8000",
    serviceToken: "service-token-value",
    timeoutMs: 500,
    fetchImpl,
  });
  return { api, captured };
}

const ctx = { requestId: "req-1", token: "session-token", clientIp: "198.51.100.4" };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("TaskboardApiClient", () => {
  it("sends service token, bearer token, request id and client ip", async () => {
    const { api, captured } = client(() => json({ id: "u1" }));
    await api.me(ctx);
    const [call] = captured;
    expect(call?.url).toBe("http://api.test:8000/api/v1/auth/me");
    const headers = new Headers(call?.init.headers);
    expect(headers.get("x-service-token")).toBe("service-token-value");
    expect(headers.get("authorization")).toBe("Bearer session-token");
    expect(headers.get("x-request-id")).toBe("req-1");
    expect(headers.get("x-client-ip")).toBe("198.51.100.4");
    expect(call?.init.redirect).toBe("error");
  });

  it("omits optional headers and encodes path segments and query values", async () => {
    const { api, captured } = client(() => json({ items: [], page: 1, page_size: 20, total: 0 }));
    await api.listTasks({ requestId: "r" }, "../admin", { q: "a&b=c", status: "todo", label: "" });
    const [call] = captured;
    expect(call?.url).toBe(
      "http://api.test:8000/api/v1/projects/..%2Fadmin/tasks?q=a%26b%3Dc&status=todo",
    );
    const headers = new Headers(call?.init.headers);
    expect(headers.has("authorization")).toBe(false);
    expect(headers.has("x-client-ip")).toBe(false);
  });

  it("serialises JSON bodies", async () => {
    const { api, captured } = client(() => json({ id: "t1" }, 201));
    await api.createTeam(ctx, "Core");
    expect(captured[0]?.init.method).toBe("POST");
    expect(captured[0]?.init.body).toBe(JSON.stringify({ name: "Core" }));
    expect(new Headers(captured[0]?.init.headers).get("content-type")).toBe("application/json");
  });

  it("maps error bodies to ApiError with fields", async () => {
    const { api } = client(() =>
      json(
        { error: { code: "validation_failed", message: "bad", fields: { email: "taken", n: 1 } } },
        422,
      ),
    );
    const error = await api
      .register(ctx, { email: "a@b.c", display_name: "A", password: "x" })
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      code: "validation_failed",
      fields: { email: "taken" },
    });
    expect((error as ApiError).isValidation).toBe(true);
  });

  it("tolerates non-JSON error bodies", async () => {
    const { api } = client(() => new Response("upstream exploded", { status: 502 }));
    const error = await api.listTeams(ctx).catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 502, code: "error", message: "API error 502" });
  });

  it("turns network failures into a 503 without leaking details", async () => {
    const { api } = client(() => Promise.reject(new Error("ECONNREFUSED 10.0.0.1:8000")));
    const error = await api.listTeams(ctx).catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 503, code: "api_unavailable" });
    expect((error as Error).message).not.toContain("10.0.0.1");
  });

  it("returns empty responses and binary downloads", async () => {
    const { api, captured } = client((url) =>
      url.endsWith("/download")
        ? new Response("file-bytes", {
            headers: {
              "content-type": "application/octet-stream",
              "content-disposition": 'attachment; filename="a.txt"',
              "content-length": "10",
            },
          })
        : new Response(null, { status: 204 }),
    );
    await api.deleteTask(ctx, "t1");
    expect(captured[0]?.init.method).toBe("DELETE");
    const download = await api.downloadAttachment(ctx, "a1");
    expect(download.contentDisposition).toBe('attachment; filename="a.txt"');
    expect(download.contentLength).toBe("10");
    expect(await new Response(download.body).text()).toBe("file-bytes");
  });

  it("uploads files as multipart form data", async () => {
    const { api, captured } = client(() => json({ id: "a1" }, 201));
    await api.uploadAttachment(ctx, "t1", {
      filename: "notes.txt",
      contentType: "text/plain",
      data: Buffer.from("hello"),
    });
    const body = captured[0]?.init.body;
    expect(body).toBeInstanceOf(FormData);
    const file = (body as FormData).get("file") as File;
    expect(file.name).toBe("notes.txt");
    expect(await file.text()).toBe("hello");
  });

  it("calls every endpoint with the right method and path", async () => {
    const { api, captured } = client(() => json({ items: [], page: 1, page_size: 20, total: 0 }));
    const calls: [() => Promise<unknown>, string, string][] = [
      [() => api.login(ctx, { email: "e", password: "p" }), "POST", "/auth/login"],
      [() => api.logout(ctx), "POST", "/auth/logout"],
      [
        () => api.changePassword(ctx, { current_password: "a", new_password: "b" }),
        "POST",
        "/auth/password/change",
      ],
      [() => api.forgotPassword(ctx, "e"), "POST", "/auth/password/forgot"],
      [
        () => api.resetPassword(ctx, { token: "t", new_password: "b" }),
        "POST",
        "/auth/password/reset",
      ],
      [() => api.getTeam(ctx, "t"), "GET", "/teams/t"],
      [() => api.addMember(ctx, "t", "e"), "POST", "/teams/t/members"],
      [() => api.removeMember(ctx, "t", "u"), "DELETE", "/teams/t/members/u"],
      [() => api.listTeamProjects(ctx, "t"), "GET", "/teams/t/projects"],
      [
        () => api.createProject(ctx, "t", { name: "n", webhook_url: null }),
        "POST",
        "/teams/t/projects",
      ],
      [() => api.listMyProjects(ctx), "GET", "/projects"],
      [() => api.getProject(ctx, "p"), "GET", "/projects/p"],
      [() => api.updateProject(ctx, "p", { name: "n" }), "PATCH", "/projects/p"],
      [() => api.archiveProject(ctx, "p"), "POST", "/projects/p/archive"],
      [
        () =>
          api.createTask(ctx, "p", {
            title: "t",
            description: "",
            status: "todo",
            priority: "low",
            assignee_id: null,
            due_date: null,
            labels: [],
          }),
        "POST",
        "/projects/p/tasks",
      ],
      [() => api.exportCsv(ctx, "p"), "GET", "/projects/p/export.csv"],
      [() => api.projectActivity(ctx, "p", 2), "GET", "/projects/p/activity?page=2&page_size=50"],
      [() => api.getTask(ctx, "t"), "GET", "/tasks/t"],
      [() => api.updateTask(ctx, "t", { status: "done" }), "PATCH", "/tasks/t"],
      [() => api.listComments(ctx, "t"), "GET", "/tasks/t/comments"],
      [() => api.addComment(ctx, "t", "b"), "POST", "/tasks/t/comments"],
      [() => api.updateComment(ctx, "c", "b"), "PATCH", "/comments/c"],
      [() => api.deleteComment(ctx, "c"), "DELETE", "/comments/c"],
      [() => api.listAttachments(ctx, "t"), "GET", "/tasks/t/attachments"],
      [() => api.searchTasks(ctx, { q: "x" }), "GET", "/search/tasks?q=x"],
      [
        () => api.listUsers(ctx, { q: "a", page: 1 }),
        "GET",
        "/admin/users?q=a&page=1&page_size=50",
      ],
      [() => api.updateUser(ctx, "u", { role: "admin" }), "PATCH", "/admin/users/u"],
      [() => api.globalActivity(ctx, 1), "GET", "/admin/activity?page=1&page_size=50"],
    ];
    for (const [call, method, path] of calls) {
      await call();
      const last = captured.at(-1);
      expect(last?.init.method).toBe(method);
      expect(last?.url).toBe(`http://api.test:8000/api/v1${path}`);
    }
  });

  it("reports readiness", async () => {
    expect(await client(() => new Response("{}")).api.ready("r")).toBe(true);
    expect(await client(() => new Response("{}", { status: 503 })).api.ready("r")).toBe(false);
    expect(await client(() => Promise.reject(new Error("down"))).api.ready("r")).toBe(false);
  });

  it("builds errors from odd bodies", () => {
    expect(apiErrorFrom(500, null)).toMatchObject({ code: "error", fields: {} });
    expect(apiErrorFrom(400, { error: { fields: "nope" } }).fields).toEqual({});
  });
});

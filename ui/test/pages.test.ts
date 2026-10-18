import request from "supertest";
import { describe, expect, it } from "vitest";
import { ApiError } from "../src/api/errors.js";
import type { TestWorld } from "./helpers.js";
import { csrfToken, loggedIn, makeWorld, postForm } from "./helpers.js";

async function setup(world: TestWorld) {
  const agent = await loggedIn(world);
  const created = await postForm(agent, "/teams", { name: "Core" });
  const teamId = String(created.headers.location).split("/").pop() ?? "";
  const project = await postForm(
    agent,
    `/teams/${teamId}/projects`,
    { name: "Roadmap", webhook_url: "" },
    `/teams/${teamId}`,
  );
  const projectId = String(project.headers.location).split("/").pop() ?? "";
  const task = await postForm(
    agent,
    `/projects/${projectId}/tasks`,
    {
      title: "Ship it",
      description:
        "**bold** <script>alert(1)</script> [x](javascript:alert(1)) <img src=x onerror=alert(1)> [ok](https://example.com)",
      status: "todo",
      priority: "high",
      assignee_id: "",
      due_date: "2026-12-01",
      labels: "release, ui",
    },
    `/projects/${projectId}`,
  );
  const taskId = String(task.headers.location).split("/").pop() ?? "";
  return { agent, teamId, projectId, taskId };
}

describe("pages", () => {
  it("creates a team, adds members and creates a project", async () => {
    const world = makeWorld();
    world.api.addUser("bob@example.com", "bob password 1");
    const { agent, teamId, projectId } = await setup(world);
    const team = await agent.get(`/teams/${teamId}`);
    expect(team.status).toBe(200);
    expect(team.text).toContain("Roadmap");
    const added = await postForm(
      agent,
      `/teams/${teamId}/members`,
      { email: "bob@example.com" },
      `/teams/${teamId}`,
    );
    expect(added.headers.location).toBe(`/teams/${teamId}`);
    expect((await agent.get(`/teams/${teamId}`)).text).toContain("Member added.");
    const missing = await postForm(
      agent,
      `/teams/${teamId}/members`,
      { email: "ghost@example.com" },
      `/teams/${teamId}`,
    );
    expect(missing.status).toBe(303);
    const bob = [...world.api.users.values()].find((u) => u.email === "bob@example.com");
    const removed = await postForm(
      agent,
      `/teams/${teamId}/members/${bob?.id ?? ""}/remove`,
      {},
      `/teams/${teamId}`,
    );
    expect(removed.headers.location).toBe(`/teams/${teamId}`);
    expect(
      (await postForm(agent, `/teams/${teamId}/members`, { email: "nope" }, `/teams/${teamId}`))
        .status,
    ).toBe(303);
    const http = await postForm(
      agent,
      `/teams/${teamId}/projects`,
      { name: "Hooks", webhook_url: "http://insecure.example" },
      `/teams/${teamId}`,
    );
    expect(http.headers.location).toBe(`/teams/${teamId}`);
    expect((await agent.get(`/teams/${teamId}`)).text).toContain("webhook URL must use https");
    expect(
      (await postForm(agent, `/teams/${teamId}/projects`, { name: "" }, `/teams/${teamId}`)).status,
    ).toBe(303);
    expect((await postForm(agent, "/teams", { name: "" })).headers.location).toBe("/");
    expect(projectId).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("renders the board, settings, archive and activity", async () => {
    const world = makeWorld();
    const { agent, projectId } = await setup(world);
    const board = await agent.get(`/projects/${projectId}`);
    expect(board.status).toBe(200);
    expect(board.text).toContain("To do");
    expect(board.text).toContain("Ship it");
    expect(board.text).toContain("Project settings");
    const saved = await postForm(
      agent,
      `/projects/${projectId}/settings`,
      { name: "Renamed", webhook_url: "https://hooks.example.com/x" },
      `/projects/${projectId}`,
    );
    expect(saved.status).toBe(303);
    const after = await agent.get(`/projects/${projectId}`);
    expect(after.text).toContain("Renamed");
    expect(after.text).toContain("secret-value");
    expect(
      (
        await postForm(
          agent,
          `/projects/${projectId}/settings`,
          { name: "" },
          `/projects/${projectId}`,
        )
      ).status,
    ).toBe(303);
    const activity = await agent.get(`/projects/${projectId}/activity?page=x`);
    expect(activity.status).toBe(200);
    expect(activity.text).toContain("created task &#34;&lt;b&gt;Ship&lt;/b&gt;&#34;");
    const bad = await postForm(
      agent,
      `/projects/${projectId}/tasks`,
      { title: "", status: "nope" },
      `/projects/${projectId}`,
    );
    expect(bad.headers.location).toBe(`/projects/${projectId}`);
    expect(
      (await postForm(agent, `/projects/${projectId}/archive`, {}, `/projects/${projectId}`))
        .status,
    ).toBe(303);
    const archived = await agent.get(`/projects/${projectId}`);
    expect(archived.text).toContain("archived, read-only");
    expect(archived.text).not.toContain("New task");
    const blocked = await postForm(
      agent,
      `/projects/${projectId}/tasks`,
      { title: "late" },
      `/projects/${projectId}`,
    );
    expect(blocked.headers.location).toBe(`/projects/${projectId}`);
    expect((await agent.get(`/projects/${projectId}`)).text).toContain("archived and read-only");
  });

  it("renders task Markdown safely", async () => {
    const world = makeWorld();
    const { agent, taskId } = await setup(world);
    const page = await agent.get(`/tasks/${taskId}`);
    expect(page.status).toBe(200);
    // The rendered description; the edit form below holds the raw Markdown, HTML-escaped.
    const rendered =
      /<section class="card markdown">([\s\S]*?)<\/section>/.exec(page.text)?.[1] ?? "";
    expect(rendered).toContain("<strong>bold</strong>");
    expect(rendered).not.toContain("<script");
    expect(rendered).not.toContain("javascript:");
    expect(rendered).not.toContain("onerror");
    expect(rendered).toContain(
      '<a href="https://example.com" rel="noopener noreferrer nofollow">ok</a>',
    );
    expect(page.text).not.toContain("<script>alert(1)</script>");
    expect(page.text).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });

  it("edits tasks, statuses and comments", async () => {
    const world = makeWorld();
    const { agent, taskId, projectId } = await setup(world);
    const from = `/tasks/${taskId}`;
    expect(
      (await postForm(agent, `/tasks/${taskId}/status`, { status: "done" }, from)).status,
    ).toBe(303);
    expect(world.api.tasks.get(taskId)?.status).toBe("done");
    expect(
      (await postForm(agent, `/tasks/${taskId}/status`, { status: "weird" }, from)).status,
    ).toBe(303);
    await postForm(
      agent,
      `/tasks/${taskId}`,
      { title: "Renamed", status: "in_progress", priority: "low", labels: "a" },
      from,
    );
    expect(world.api.tasks.get(taskId)?.title).toBe("Renamed");
    await postForm(agent, `/tasks/${taskId}`, { title: "", due_date: "tomorrow" }, from);
    expect(world.api.tasks.get(taskId)?.title).toBe("Renamed");
    await postForm(agent, `/tasks/${taskId}/comments`, { body: "**hi** <script>x</script>" }, from);
    await postForm(agent, `/tasks/${taskId}/comments`, { body: "   " }, from);
    const [comment] = [...world.api.comments.values()];
    const page = await agent.get(from);
    expect(page.text).toContain("<strong>hi</strong>");
    expect(page.text).not.toContain("<script>x</script>");
    expect(page.text).toContain("Save comment");
    await postForm(
      agent,
      `/comments/${comment?.id ?? ""}`,
      { body: "edited", task_id: taskId },
      from,
    );
    expect(world.api.comments.get(comment?.id ?? "")?.body).toBe("edited");
    expect((await agent.get(from)).text).toContain("edited");
    expect(
      (
        await postForm(
          agent,
          `/comments/${comment?.id ?? ""}`,
          { body: "x", task_id: "not-a-uuid" },
          from,
        )
      ).headers.location,
    ).toBe("/");
    await postForm(agent, `/comments/${comment?.id ?? ""}/delete`, { task_id: taskId }, from);
    expect(world.api.comments.size).toBe(0);
    const deleted = await postForm(agent, `/tasks/${taskId}/delete`, {}, from);
    expect(deleted.headers.location).toBe(`/projects/${projectId}`);
  });

  it("does not let others edit a comment", async () => {
    const world = makeWorld();
    const { agent, taskId, teamId } = await setup(world);
    await postForm(agent, `/tasks/${taskId}/comments`, { body: "mine" }, `/tasks/${taskId}`);
    world.api.addUser("bob@example.com", "bob password 1");
    await postForm(
      agent,
      `/teams/${teamId}/members`,
      { email: "bob@example.com" },
      `/teams/${teamId}`,
    );
    const bob = await loggedIn(world, "bob@example.com", "bob password 1");
    const page = await bob.get(`/tasks/${taskId}`);
    expect(page.text).not.toContain("Save comment");
    const [comment] = [...world.api.comments.values()];
    await postForm(
      bob,
      `/comments/${comment?.id ?? ""}`,
      { body: "hijack", task_id: taskId },
      `/tasks/${taskId}`,
    );
    expect(world.api.comments.get(comment?.id ?? "")?.body).toBe("mine");
    expect((await bob.get(`/tasks/${taskId}`)).text).toContain(
      "only the author can change this comment",
    );
  });

  it("uploads and downloads attachments safely", async () => {
    const world = makeWorld();
    const { agent, taskId } = await setup(world);
    const token = await csrfToken(agent, `/tasks/${taskId}`);
    const upload = await agent
      .post(`/tasks/${taskId}/attachments`)
      .field("_csrf", token)
      .attach("file", Buffer.from("<html>hi</html>"), {
        filename: "page.html",
        contentType: "text/html",
      });
    expect(upload.status).toBe(303);
    const [attachment] = [...world.api.attachments.values()];
    expect(attachment?.filename).toBe("page.html");
    const download = await agent.get(`/attachments/${attachment?.id ?? ""}/download`);
    expect(download.status).toBe(200);
    expect(download.headers["content-type"]).toBe("application/octet-stream");
    expect(download.headers["content-disposition"]).toBe('attachment; filename="page.html"');
    expect(download.headers["x-content-type-options"]).toBe("nosniff");
    expect(download.body).toEqual(Buffer.from("<html>hi</html>"));

    const tooBig = await agent
      .post(`/tasks/${taskId}/attachments`)
      .field("_csrf", token)
      .attach("file", Buffer.alloc(2048), "big.bin");
    expect(tooBig.status).toBe(413);
    const noToken = await agent
      .post(`/tasks/${taskId}/attachments`)
      .attach("file", Buffer.from("x"), "x.txt");
    expect(noToken.status).toBe(403);
    const missingFile = await agent.post(`/tasks/${taskId}/attachments`).field("_csrf", token);
    expect(missingFile.status).toBe(303);
    const elsewhere = await agent
      .post("/teams")
      .field("_csrf", token)
      .attach("file", Buffer.from("x"), "x.txt");
    expect(elsewhere.status).toBe(415);
    const twoFiles = await agent
      .post(`/tasks/${taskId}/attachments`)
      .field("_csrf", token)
      .attach("file", Buffer.from("a"), "a.txt")
      .attach("file", Buffer.from("b"), "b.txt");
    expect(twoFiles.status).toBe(400);
  });

  it("streams the CSV export", async () => {
    const world = makeWorld();
    const { agent, projectId } = await setup(world);
    const response = await agent.get(`/projects/${projectId}/export.csv`);
    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toBe("text/csv; charset=utf-8");
    expect(response.headers["content-disposition"]).toContain("Roadmap-tasks.csv");
  });

  it("searches with filters and paginates", async () => {
    const world = makeWorld();
    const { agent } = await setup(world);
    const empty = await agent.get("/search");
    expect(empty.status).toBe(200);
    expect(
      world.api.calls.some(
        (c) => c.method === "searchTasks" && (c.args[0] as { q?: string }).q !== undefined,
      ),
    ).toBe(false);
    const found = await agent.get("/search?q=Ship&status=bogus&sort=title%3BDROP&order=asc&page=1");
    expect(found.status).toBe(200);
    expect(found.text).toContain("1 result");
    const call = world.api.calls.filter((c) => c.method === "searchTasks").at(-1);
    expect(call?.args[0]).toMatchObject({ q: "Ship", order: "asc", page: 1, page_size: 20 });
    expect(call?.args[0]).not.toHaveProperty("status", "bogus");
    expect((call?.args[0] as { sort?: string }).sort).toBeUndefined();
  });

  it("guards ids, admin pages and profile", async () => {
    const world = makeWorld();
    const agent = await loggedIn(world);
    expect((await agent.get("/teams/not-a-uuid")).status).toBe(404);
    expect((await agent.get("/tasks/..%2F..%2Fadmin")).status).toBe(404);
    expect((await agent.get("/teams/00000000-0000-0000-0000-000000000000")).status).toBe(404);
    expect((await agent.get("/admin/users")).status).toBe(403);
    expect((await agent.get("/nope")).status).toBe(404);
    const profile = await agent.get("/profile");
    expect(profile.text).toContain("olive@example.com");
    const wrong = await postForm(
      agent,
      "/profile/password",
      {
        current_password: "wrong password",
        new_password: "new password 12",
        new_password_confirm: "new password 12",
      },
      "/profile",
    );
    expect(wrong.status).toBe(422);
    expect(wrong.text).toContain("current password is incorrect");
    const mismatch = await postForm(
      agent,
      "/profile/password",
      { current_password: "x", new_password: "new password 12", new_password_confirm: "other" },
      "/profile",
    );
    expect(mismatch.status).toBe(422);
    const ok = await postForm(
      agent,
      "/profile/password",
      {
        current_password: "olive password 1",
        new_password: "new password 12",
        new_password_confirm: "new password 12",
      },
      "/profile",
    );
    expect(ok.headers.location).toBe("/profile");
  });

  it("lets admins manage users and see all activity", async () => {
    const world = makeWorld();
    const member = world.api.addUser("bob@example.com", "bob password 1");
    const admin = await loggedIn(world, "root@example.com", "root password 1", "admin");
    const users = await admin.get("/admin/users?q=bob&page=1");
    expect(users.status).toBe(200);
    expect(users.text).toContain("bob@example.com");
    await postForm(admin, `/admin/users/${member.id}`, { is_active: "false" }, "/admin/users");
    expect(world.api.users.get(member.id)?.is_active).toBe(false);
    await postForm(admin, `/admin/users/${member.id}`, { role: "admin" }, "/admin/users");
    expect(world.api.users.get(member.id)?.role).toBe("admin");
    const nothing = await postForm(
      admin,
      `/admin/users/${member.id}`,
      { role: "root" },
      "/admin/users",
    );
    expect(nothing.headers.location).toBe("/admin/users");
    expect((await admin.get("/admin/activity")).status).toBe(200);
  });

  it("shows friendly error pages", async () => {
    const world = makeWorld();
    const agent = await loggedIn(world);
    world.api.failWith = new ApiError(503, "api_unavailable", "down");
    const unavailable = await agent.get("/");
    expect(unavailable.status).toBe(503);
    expect(unavailable.text).toContain("Service unavailable");
    world.api.failWith = new ApiError(500, "internal_error", "stack trace here");
    const broken = await agent.get("/");
    expect(broken.status).toBe(500);
    expect(broken.text).not.toContain("stack trace here");
    const { taskId } = await setup(world);
    world.api.failWith = null;
    const res = await agent.get(`/tasks/${taskId}`);
    expect([200, 404]).toContain(res.status);
  });
});

describe("headers and probes", () => {
  it("sets strict security headers and no-store on pages", async () => {
    const { app } = makeWorld({ cookieSecure: true });
    const response = await request(app).get("/login");
    const csp = String(response.headers["content-security-policy"]);
    expect(csp).toContain("script-src 'none'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("upgrade-insecure-requests");
    expect(response.headers["strict-transport-security"]).toContain("max-age=31536000");
    expect(response.headers["x-content-type-options"]).toBe("nosniff");
    expect(response.headers["referrer-policy"]).toBe("no-referrer");
    expect(response.headers["cache-control"]).toBe("no-store");
    expect(response.headers["x-powered-by"]).toBeUndefined();
    expect(response.headers["x-request-id"]).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("omits HSTS on plain HTTP and serves static assets", async () => {
    const { app } = makeWorld();
    const page = await request(app).get("/login");
    expect(page.headers["strict-transport-security"]).toBeUndefined();
    const css = await request(app).get("/static/styles.css");
    expect(css.status).toBe(200);
  });

  it("answers health and readiness probes", async () => {
    const world = makeWorld();
    expect((await request(world.app).get("/healthz")).body).toEqual({ status: "ok" });
    expect((await request(world.app).get("/readyz")).status).toBe(200);
    world.api.isReady = false;
    const ready = await request(world.app).get("/readyz");
    expect(ready.status).toBe(503);
    expect(ready.body).toEqual({ status: "not_ready", checks: { api: "unavailable" } });
  });
});

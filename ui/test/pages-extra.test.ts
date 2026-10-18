import request from "supertest";
import { describe, expect, it } from "vitest";
import { ApiError } from "../src/api/errors.js";
import { csrfToken, loggedIn, makeWorld, postForm, setupBoard } from "./helpers.js";

describe("files, search, guards and errors", () => {
  it("uploads and downloads attachments safely", async () => {
    const world = makeWorld();
    const { agent, taskId } = await setupBoard(world);
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
    const { agent, projectId } = await setupBoard(world);
    const response = await agent.get(`/projects/${projectId}/export.csv`);
    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toBe("text/csv; charset=utf-8");
    expect(response.headers["content-disposition"]).toContain("Roadmap-tasks.csv");
  });

  it("searches with filters and paginates", async () => {
    const world = makeWorld();
    const { agent } = await setupBoard(world);
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
    const { taskId } = await setupBoard(world);
    world.api.failWith = null;
    const res = await agent.get(`/tasks/${taskId}`);
    expect([200, 404]).toContain(res.status);
  });
});

describe("API errors on page loads", () => {
  it("maps API statuses to pages without leaking detail", async () => {
    const world = makeWorld();
    const { agent, teamId } = await setupBoard(world);
    const page = `/teams/${teamId}`;
    // The first API call of a page load is /auth/me; fail the second one.
    const failSecond = async (error: ApiError) => {
      const original = world.api.me.bind(world.api);
      world.api.me = async (ctx) => {
        const user = await original(ctx);
        world.api.failWith = error;
        return user;
      };
      const response = await agent.get(page);
      world.api.me = original;
      return response;
    };
    expect((await failSecond(new ApiError(403, "forbidden", "x"))).status).toBe(403);
    expect((await failSecond(new ApiError(404, "not_found", "x"))).text).toContain("Not found");
    const conflict = await failSecond(new ApiError(409, "conflict", "the project is archived"));
    expect(conflict.status).toBe(409);
    expect(conflict.text).toContain("the project is archived");
    const expired = await failSecond(new ApiError(401, "unauthenticated", "expired"));
    expect(expired.status).toBe(303);
    expect(expired.headers.location).toBe("/login");
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

import request from "supertest";
import { describe, expect, it } from "vitest";
import { ApiError } from "../src/api/errors.js";
import { PUBLIC_ORIGIN, csrfToken, loggedIn, makeWorld, postForm } from "./helpers.js";

function cookieHeader(response: request.Response, name: string): string {
  const raw = response.headers["set-cookie"] as unknown;
  const cookies = Array.isArray(raw) ? (raw as string[]) : [];
  return cookies.find((c) => c.startsWith(`${name}=`)) ?? "";
}

describe("authentication pages", () => {
  it("issues an HttpOnly SameSite CSRF cookie with the login form", async () => {
    const { app } = makeWorld();
    const response = await request(app).get("/login");
    expect(response.status).toBe(200);
    const cookie = cookieHeader(response, "tb_csrf");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=Lax");
    expect(response.text).toContain('name="_csrf"');
  });

  it("rejects posts without a CSRF token, with a forged token, or from another origin", async () => {
    const world = makeWorld();
    world.api.addUser("olive@example.com", "olive password 1");
    const agent = request.agent(world.app);
    const token = await csrfToken(agent);
    const creds = { email: "olive@example.com", password: "olive password 1" };
    expect((await agent.post("/login").type("form").send(creds)).status).toBe(403);
    expect(
      (
        await agent
          .post("/login")
          .type("form")
          .send({ ...creds, _csrf: "forged" })
      ).status,
    ).toBe(403);
    const crossSite = await agent
      .post("/login")
      .set("Origin", "https://evil.example")
      .type("form")
      .send({ ...creds, _csrf: token });
    expect(crossSite.status).toBe(403);
    const fresh = await request(world.app)
      .post("/login")
      .type("form")
      .send({ ...creds, _csrf: token });
    expect(fresh.status).toBe(403);
    const json = await agent
      .post("/login")
      .set("Content-Type", "application/json")
      .send(JSON.stringify(creds));
    expect(json.status).toBe(403);
    expect(world.api.calls.filter((c) => c.method === "login")).toHaveLength(0);
  });

  it("logs in with secure cookie flags and lands on the dashboard", async () => {
    const world = makeWorld({ cookieSecure: true });
    world.api.addUser("olive@example.com", "olive password 1");
    // The test client never sends Secure cookies over plain HTTP, so carry the CSRF cookie by hand.
    const form = await request(world.app).get("/login");
    const csrfCookie = cookieHeader(form, "tb_csrf").split(";")[0] ?? "";
    expect(cookieHeader(form, "tb_csrf")).toContain("Secure");
    const token = /name="_csrf" value="([^"]+)"/.exec(form.text)?.[1] ?? "";
    const response = await request(world.app)
      .post("/login")
      .set("Origin", PUBLIC_ORIGIN)
      .set("Cookie", csrfCookie)
      .type("form")
      .send({ email: "Olive@Example.com", password: "olive password 1", _csrf: token });
    expect(response.status).toBe(303);
    expect(response.headers.location).toBe("/");
    const session = cookieHeader(response, "tb_session");
    expect(session).toContain("HttpOnly");
    expect(session).toContain("Secure");
    expect(session).toContain("SameSite=Lax");
    expect(cookieHeader(response, "tb_csrf")).not.toBe("");
    expect(world.api.calls.find((c) => c.method === "login")?.args[0]).toEqual({
      email: "olive@example.com",
      password: "olive password 1",
    });
  });

  it("shows a generic message for bad credentials and never echoes the password", async () => {
    const world = makeWorld();
    const agent = request.agent(world.app);
    const token = await csrfToken(agent);
    const response = await agent
      .post("/login")
      .type("form")
      .send({ email: "nobody@example.com", password: "secret-attempt-123", _csrf: token });
    expect(response.status).toBe(401);
    expect(response.text).toContain("Invalid email or password.");
    expect(response.text).not.toContain("secret-attempt-123");
  });

  it("shows rate limiting and validation errors on the login form", async () => {
    const world = makeWorld();
    const agent = request.agent(world.app);
    const invalid = await postForm(
      agent,
      "/login",
      { email: "not-an-email", password: "" },
      "/login",
    );
    expect(invalid.status).toBe(422);
    world.api.failWith = new ApiError(429, "rate_limited", "too many attempts");
    const limited = await postForm(
      agent,
      "/login",
      { email: "a@example.com", password: "x" },
      "/login",
    );
    expect(limited.status).toBe(429);
    expect(limited.text).toContain("Too many attempts");
  });

  it("redirects anonymous visitors and signed-in visitors appropriately", async () => {
    const world = makeWorld();
    const anonymous = await request(world.app).get("/");
    expect(anonymous.status).toBe(303);
    expect(anonymous.headers.location).toBe("/login");
    const agent = await loggedIn(world);
    const dashboard = await agent.get("/");
    expect(dashboard.status).toBe(200);
    expect(dashboard.text).toContain("Welcome back");
    expect((await agent.get("/login")).status).toBe(303);
  });

  it("clears a session the API no longer accepts", async () => {
    const world = makeWorld();
    const agent = await loggedIn(world);
    world.api.sessions.clear();
    const response = await agent.get("/");
    expect(response.status).toBe(303);
    expect(cookieHeader(response, "tb_session")).toContain("Expires=Thu, 01 Jan 1970");
  });

  it("logs out and revokes the API session", async () => {
    const world = makeWorld();
    const agent = await loggedIn(world);
    const response = await postForm(agent, "/logout", {});
    expect(response.status).toBe(303);
    expect(world.api.sessions.size).toBe(0);
    expect((await agent.get("/")).headers.location).toBe("/login");
    const again = await postForm(agent, "/logout", {}, "/login");
    expect(again.status).toBe(303);
  });

  it("registers with validation and conflict messages", async () => {
    const world = makeWorld();
    const agent = request.agent(world.app);
    const mismatch = await postForm(
      agent,
      "/register",
      {
        email: "ada@example.com",
        display_name: "Ada",
        password: "long enough 1",
        password_confirm: "different 1",
      },
      "/register",
    );
    expect(mismatch.status).toBe(422);
    expect(mismatch.text).toContain("Passwords do not match");
    expect(mismatch.text).not.toContain("long enough 1");
    expect(mismatch.text).toContain('value="ada@example.com"');
    const fields = {
      email: "ada@example.com",
      display_name: "Ada",
      password: "long enough 1",
      password_confirm: "long enough 1",
    };
    const created = await postForm(agent, "/register", fields, "/register");
    expect(created.status).toBe(303);
    expect(created.headers.location).toBe("/login");
    const duplicate = await postForm(agent, "/register", fields, "/register");
    expect(duplicate.status).toBe(409);
    expect(duplicate.text).toContain("already exists");
  });

  it("handles forgot and reset password", async () => {
    const world = makeWorld();
    const agent = request.agent(world.app);
    expect(
      (await postForm(agent, "/forgot-password", { email: "bad" }, "/forgot-password")).status,
    ).toBe(422);
    const sent = await postForm(
      agent,
      "/forgot-password",
      { email: "ada@example.com" },
      "/forgot-password",
    );
    expect(sent.status).toBe(303);
    expect(world.api.outbox).toEqual(["ada@example.com"]);
    world.api.failWith = new ApiError(429, "rate_limited", "too many attempts");
    const limited = await postForm(
      agent,
      "/forgot-password",
      { email: "ada@example.com" },
      "/forgot-password",
    );
    expect(limited.headers.location).toBe("/forgot-password");

    expect((await agent.get("/reset-password?token=<script>")).status).toBe(400);
    const page = "/reset-password?token=valid-reset-token-0123456789";
    const form = await agent.get(page);
    expect(form.text).toContain('value="valid-reset-token-0123456789"');
    const mismatch = await postForm(
      agent,
      "/reset-password",
      { token: "valid-reset-token-0123456789", password: "new password 1", password_confirm: "x" },
      page,
    );
    expect(mismatch.status).toBe(422);
    const rejected = await postForm(
      agent,
      "/reset-password",
      {
        token: "expired-reset-token-000000",
        password: "new password 1",
        password_confirm: "new password 1",
      },
      page,
    );
    expect(rejected.status).toBe(422);
    expect(rejected.text).toContain("invalid or has expired");
    const done = await postForm(
      agent,
      "/reset-password",
      {
        token: "valid-reset-token-0123456789",
        password: "new password 1",
        password_confirm: "new password 1",
      },
      page,
    );
    expect(done.status).toBe(303);
  });
});

import { Writable } from "node:stream";
import { describe, expect, it } from "vitest";
import { loadConfig } from "../src/config.js";
import { createLogger, requestContext } from "../src/logger.js";
import { parseForm, registerForm, safeValues, searchQuery, taskForm } from "../src/forms.js";
import { MarkdownRenderer } from "../src/views/MarkdownRenderer.js";
import { formatBytes, formatDateTime, queryString } from "../src/views/format.js";
import { ActivityViewBuilder, SearchViewBuilder } from "../src/views/ViewModels.js";
import type { Activity } from "../src/api/types.js";

const env = {
  API_BASE_URL: "http://api:8000/",
  SERVICE_TOKEN: "s".repeat(32),
  UI_SECRET: "u".repeat(32),
  PUBLIC_URL: "https://taskboard.example/some/path",
};

describe("config", () => {
  it("parses and normalises values with defaults", () => {
    const config = loadConfig(env);
    expect(config.apiBaseUrl).toBe("http://api:8000");
    expect(config.publicOrigin).toBe("https://taskboard.example");
    expect(config.cookieSecure).toBe(true);
    expect(config.port).toBe(3000);
    expect(config.host).toBe("127.0.0.1");
    expect(loadConfig({ ...env, COOKIE_SECURE: "false", PORT: "8080" })).toMatchObject({
      cookieSecure: false,
      port: 8080,
    });
  });

  it("lists every problem", () => {
    expect(() => loadConfig({ ...env, SERVICE_TOKEN: "short", PUBLIC_URL: "nope" })).toThrow(
      /SERVICE_TOKEN.*PUBLIC_URL|PUBLIC_URL.*SERVICE_TOKEN/,
    );
  });
});

describe("logger", () => {
  it("writes JSON lines with the request id and redacts secrets", async () => {
    const lines: string[] = [];
    const sink = new Writable({
      write(chunk: Buffer, _encoding, callback) {
        lines.push(chunk.toString());
        callback();
      },
    });
    const logger = createLogger("info", sink);
    requestContext.run({ requestId: "req-42" }, () => {
      logger.info({ password: "hunter2", token: "abc" }, "hello");
    });
    logger.info("outside");
    await new Promise((resolve) => setImmediate(resolve));
    const first = JSON.parse(lines[0] ?? "{}") as Record<string, unknown>;
    expect(first).toMatchObject({
      message: "hello",
      request_id: "req-42",
      service: "ui",
      level: "info",
    });
    expect(first.password).toBe("[redacted]");
    expect(first.token).toBe("[redacted]");
    expect(JSON.parse(lines[1] ?? "{}")).toMatchObject({ request_id: "-" });
  });
});

describe("forms", () => {
  it("normalises task input", () => {
    const result = parseForm(taskForm, {
      title: " T ",
      labels: "a, b ,, c",
      assignee_id: "",
      due_date: "",
    });
    expect(result).toEqual({
      ok: true,
      data: {
        title: "T",
        description: "",
        status: "todo",
        priority: "medium",
        assignee_id: null,
        due_date: null,
        labels: ["a", "b", "c"],
      },
    });
  });

  it("reports errors without secrets", () => {
    const result = parseForm(registerForm, {
      email: "x",
      display_name: "A",
      password: "short",
      password_confirm: "short",
      _csrf: "t",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(Object.keys(result.errors).sort()).toEqual(["email", "password"]);
      expect(result.values).toEqual({ email: "x", display_name: "A" });
    }
    expect(safeValues(null)).toEqual({});
    expect(parseForm(registerForm, undefined).ok).toBe(false);
  });

  it("drops invalid search parameters instead of failing", () => {
    expect(
      searchQuery.parse({ status: "nope", sort: "x", page: "-1", q: "hi", assignee_id: "bad" }),
    ).toEqual({
      q: "hi",
    });
  });
});

describe("markdown", () => {
  const renderer = new MarkdownRenderer();

  it.each([
    ["<script>alert(1)</script>", "<script"],
    ["[x](javascript:alert(1))", "javascript:"],
    ["<img src=x onerror=alert(1)>", "onerror"],
    ['<a href="//evil.example">x</a>', "//evil.example"],
    ["<iframe src=https://evil.example></iframe>", "<iframe"],
    ['<p style="position:fixed">x</p>', "style="],
    ["[x](data:text/html;base64,PHNjcmlwdD4=)", "data:"],
  ])("strips %s", (input, forbidden) => {
    expect(renderer.render(input)).not.toContain(forbidden);
  });

  it("keeps ordinary Markdown", () => {
    const html = renderer.render("# Title\n\n- **a**\n- `b`\n\n[link](https://example.com)");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<strong>a</strong>");
    expect(html).toContain("<code>b</code>");
    expect(html).toContain('rel="noopener noreferrer nofollow"');
  });
});

describe("view models", () => {
  it("formats values", () => {
    expect(formatBytes(10)).toBe("10 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
    expect(formatDateTime("2026-10-18T09:15:00Z")).toBe("2026-10-18 09:15");
    expect(formatDateTime("not a date")).toBe("not a date");
    expect(queryString({ a: "x y", b: undefined, c: "" })).toBe("?a=x+y");
    expect(queryString({})).toBe("");
  });

  it("summarises every activity type", () => {
    const base: Activity = {
      id: "1",
      actor_id: null,
      actor_name: null,
      event_type: "",
      team_id: "t",
      project_id: null,
      task_id: null,
      details: {
        title: "T",
        old_status: "todo",
        new_status: "done",
        filename: "f",
        display_name: "Bob",
      },
      created_at: "2026-10-18T09:00:00Z",
    };
    const types = [
      "task.created",
      "task.updated",
      "task.status_changed",
      "task.deleted",
      "comment.added",
      "attachment.added",
      "member.added",
      "member.removed",
      "something.else",
    ];
    const summaries = types.map((event_type) =>
      ActivityViewBuilder.summary({ ...base, event_type }),
    );
    expect(summaries).toEqual([
      'created task "T"',
      "updated a task",
      "moved a task from todo to done",
      'deleted task "T"',
      "commented on a task",
      'attached "f"',
      "added Bob to the team",
      "removed Bob from the team",
      "something.else",
    ]);
    expect(
      ActivityViewBuilder.summary({ ...base, event_type: "task.created", details: { title: 1 } }),
    ).toBe('created task ""');
  });

  it("builds search pagination links from known parameters only", () => {
    const view = new SearchViewBuilder().build(
      { q: "a&b", status: "todo" },
      { items: [], page: 2, page_size: 20, total: 45 },
    );
    expect(view.lastPage).toBe(3);
    expect(view.previousHref).toBe("/search?q=a%26b&status=todo&page=1");
    expect(view.nextHref).toBe("/search?q=a%26b&status=todo&page=3");
    expect(new SearchViewBuilder().build({}, null).results).toBeUndefined();
  });
});

describe("composition root", () => {
  it("wires the real API client into the app", async () => {
    const { composeApp } = await import("../src/composition.js");
    const { default: supertest } = await import("supertest");
    // A closed loopback port fails fast, so readiness reports the API as unavailable.
    const config = loadConfig({
      ...env,
      API_BASE_URL: "http://127.0.0.1:9",
      API_REQUEST_TIMEOUT_MS: "500",
    });
    const app = composeApp(config, createLogger("silent"));
    expect((await supertest(app).get("/healthz")).body).toEqual({ status: "ok" });
    const ready = await supertest(app).get("/readyz");
    expect(ready.status).toBe(503);
  });
});

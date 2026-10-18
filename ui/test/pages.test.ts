import { describe, expect, it } from "vitest";
import { loggedIn, makeWorld, postForm, setupBoard } from "./helpers.js";

describe("pages", () => {
  it("creates a team, adds members and creates a project", async () => {
    const world = makeWorld();
    world.api.addUser("bob@example.com", "bob password 1");
    const { agent, teamId, projectId } = await setupBoard(world);
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
    const { agent, projectId } = await setupBoard(world);
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
    const { agent, taskId } = await setupBoard(world);
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
    const { agent, taskId, projectId } = await setupBoard(world);
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
    const { agent, taskId, teamId } = await setupBoard(world);
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
});

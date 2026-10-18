import type { Express } from "express";
import request from "supertest";
import { createApp } from "../src/app.js";
import type { AppConfig } from "../src/config.js";
import { createLogger } from "../src/logger.js";
import { FakeApi } from "./FakeApi.js";

export const PUBLIC_ORIGIN = "http://ui.test";

export const testConfig: AppConfig = {
  port: 3000,
  host: "127.0.0.1",
  apiBaseUrl: "http://api.test:8000",
  serviceToken: "s".repeat(40),
  uiSecret: "u".repeat(40),
  publicOrigin: PUBLIC_ORIGIN,
  cookieSecure: false,
  trustProxy: 0,
  logLevel: "error",
  apiTimeoutMs: 1000,
  maxUploadBytes: 1024,
};

export interface TestWorld {
  app: Express;
  api: FakeApi;
}

export function makeWorld(overrides: Partial<AppConfig> = {}): TestWorld {
  const api = new FakeApi();
  const app = createApp({
    config: { ...testConfig, ...overrides },
    logger: createLogger("silent"),
    api,
  });
  return { app, api };
}

export type Agent = ReturnType<typeof request.agent>;

/** Fetch a page and pull the CSRF form token out of it. */
export async function csrfToken(agent: Agent, path = "/login"): Promise<string> {
  const response = await agent.get(path);
  const match = /name="_csrf" value="([^"]+)"/.exec(response.text);
  if (!match?.[1]) {
    throw new Error(`no CSRF token on ${path} (status ${String(response.status)})`);
  }
  return match[1];
}

/** Log in through the real form and return the agent holding the session cookie. */
export async function loggedIn(
  world: TestWorld,
  email = "olive@example.com",
  password = "olive password 1",
  role: "admin" | "member" = "member",
): Promise<Agent> {
  if (![...world.api.users.values()].some((u) => u.email === email)) {
    world.api.addUser(email, password, role);
  }
  const agent = request.agent(world.app);
  const token = await csrfToken(agent);
  const response = await agent.post("/login").type("form").send({ email, password, _csrf: token });
  if (response.status !== 303) {
    throw new Error(`login failed with ${String(response.status)}`);
  }
  return agent;
}

/** POST a form with a fresh CSRF token taken from `fromPath`. */
export async function postForm(
  agent: Agent,
  path: string,
  fields: Record<string, string>,
  fromPath = "/",
): Promise<request.Response> {
  const token = await csrfToken(agent, fromPath);
  return agent
    .post(path)
    .type("form")
    .send({ ...fields, _csrf: token });
}

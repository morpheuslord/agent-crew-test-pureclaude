import { randomUUID } from "node:crypto";
import type { ApiContext, UserChanges } from "../src/api/ApiClient.js";
import { ApiError } from "../src/api/errors.js";
import type { Activity, LoginResult, Page, User } from "../src/api/types.js";
import { FakeApiBase, page } from "./FakeApiBase.js";

/** Accounts, sessions and administration. */
export abstract class FakeAccountsApi extends FakeApiBase {
  register(ctx: ApiContext, body: { email: string; display_name: string; password: string }) {
    this.record("register", ctx, body);
    if ([...this.users.values()].some((u) => u.email === body.email)) {
      return Promise.reject(
        new ApiError(409, "conflict", "an account with this email already exists", {
          email: "already registered",
        }),
      );
    }
    const user = this.addUser(body.email, body.password);
    const stored = this.users.get(user.id);
    if (stored) {
      stored.display_name = body.display_name;
    }
    return Promise.resolve({ ...user, display_name: body.display_name });
  }

  login(ctx: ApiContext, body: { email: string; password: string }): Promise<LoginResult> {
    this.record("login", ctx, body);
    const user = [...this.users.values()].find((u) => u.email === body.email);
    if (user?.password !== body.password || !user.is_active) {
      return Promise.reject(new ApiError(401, "unauthenticated", "invalid email or password"));
    }
    const token = randomUUID();
    this.sessions.set(token, user.id);
    return Promise.resolve({
      token,
      expires_at: new Date(Date.now() + 3_600_000).toISOString(),
      user: this.publicUser(user),
    });
  }

  logout(ctx: ApiContext) {
    this.record("logout", ctx);
    this.caller(ctx);
    if (ctx.token) {
      this.sessions.delete(ctx.token);
    }
    return Promise.resolve();
  }

  me(ctx: ApiContext) {
    this.record("me", ctx);
    return Promise.resolve(this.publicUser(this.caller(ctx)));
  }

  changePassword(ctx: ApiContext, body: { current_password: string; new_password: string }) {
    this.record("changePassword", ctx, body);
    const user = this.caller(ctx);
    if (user.password !== body.current_password) {
      return Promise.reject(
        new ApiError(422, "validation_failed", "current password is incorrect", {
          current_password: "incorrect",
        }),
      );
    }
    user.password = body.new_password;
    return Promise.resolve();
  }

  forgotPassword(ctx: ApiContext, email: string) {
    this.record("forgotPassword", ctx, email);
    this.outbox.push(email);
    return Promise.resolve();
  }

  resetPassword(ctx: ApiContext, body: { token: string; new_password: string }) {
    this.record("resetPassword", ctx, body);
    if (body.token !== "valid-reset-token-0123456789") {
      return Promise.reject(
        new ApiError(422, "validation_failed", "the reset link is invalid or has expired"),
      );
    }
    return Promise.resolve();
  }

  listUsers(ctx: ApiContext, query: { q?: string | undefined; page: number }): Promise<Page<User>> {
    this.record("listUsers", ctx, query);
    if (this.caller(ctx).role !== "admin") {
      return Promise.reject(new ApiError(403, "forbidden", "admin role required"));
    }
    return Promise.resolve(
      page(
        [...this.users.values()].map((u) => this.publicUser(u)),
        query.page,
        50,
      ),
    );
  }

  updateUser(ctx: ApiContext, userId: string, body: UserChanges) {
    this.record("updateUser", ctx, userId, body);
    const user = this.users.get(userId);
    if (!user) {
      return Promise.reject(new ApiError(404, "not_found", "user not found"));
    }
    Object.assign(user, body);
    return Promise.resolve(this.publicUser(user));
  }

  globalActivity(ctx: ApiContext, pageNumber: number): Promise<Page<Activity>> {
    this.record("globalActivity", ctx, pageNumber);
    this.caller(ctx);
    return Promise.resolve(page([], pageNumber, 50));
  }

  ready(): Promise<boolean> {
    return Promise.resolve(this.isReady);
  }
}

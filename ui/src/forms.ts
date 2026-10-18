import { z } from "zod";
import { SORT_FIELDS, TASK_PRIORITIES, TASK_STATUSES } from "./api/types.js";

const email = z.string().trim().toLowerCase().max(254).pipe(z.email("Enter a valid email address"));
const name = z.string().trim().min(1, "Required").max(100, "At most 100 characters");
const newPassword = z.string().min(10, "At least 10 characters").max(128, "At most 128 characters");
const anyPassword = z.string().min(1, "Required").max(128);
const uuid = z.uuid();
const optionalUuid = z
  .string()
  .trim()
  .transform((v) => (v === "" ? null : v))
  .pipe(uuid.nullable());
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD");
const optionalDate = z
  .string()
  .trim()
  .transform((v) => (v === "" ? null : v))
  .pipe(isoDate.nullable());
const optionalUrl = z
  .string()
  .trim()
  .max(2048)
  .transform((v) => (v === "" ? null : v))
  .pipe(z.url({ protocol: /^https?$/, error: "Enter an http(s) URL" }).nullable());
const labels = z
  .string()
  .max(1000)
  .transform((v) =>
    v
      .split(",")
      .map((label) => label.trim())
      .filter((label) => label.length > 0),
  )
  .pipe(
    z.array(z.string().max(40, "Labels are at most 40 characters")).max(20, "At most 20 labels"),
  );

export const loginForm = z.object({ email, password: anyPassword });

export const registerForm = z
  .object({ email, display_name: name, password: newPassword, password_confirm: z.string() })
  .refine((v) => v.password === v.password_confirm, {
    path: ["password_confirm"],
    message: "Passwords do not match",
  });

export const forgotForm = z.object({ email });

export const resetForm = z
  .object({
    token: z.string().regex(/^[A-Za-z0-9_-]{16,200}$/, "The reset link is invalid"),
    password: newPassword,
    password_confirm: z.string(),
  })
  .refine((v) => v.password === v.password_confirm, {
    path: ["password_confirm"],
    message: "Passwords do not match",
  });

export const changePasswordForm = z
  .object({
    current_password: anyPassword,
    new_password: newPassword,
    new_password_confirm: z.string(),
  })
  .refine((v) => v.new_password === v.new_password_confirm, {
    path: ["new_password_confirm"],
    message: "Passwords do not match",
  });

export const teamForm = z.object({ name });
export const memberForm = z.object({ email });
export const projectForm = z.object({ name, webhook_url: optionalUrl.default(null) });

export const taskForm = z.object({
  title: z.string().trim().min(1, "Required").max(200, "At most 200 characters"),
  description: z.string().max(20_000, "At most 20000 characters").default(""),
  status: z.enum(TASK_STATUSES).default("todo"),
  priority: z.enum(TASK_PRIORITIES).default("medium"),
  assignee_id: optionalUuid.default(null),
  due_date: optionalDate.default(null),
  labels: labels.default([]),
});

export const statusForm = z.object({ status: z.enum(TASK_STATUSES) });

export const commentForm = z.object({
  body: z.string().trim().min(1, "Write something first").max(10_000, "At most 10000 characters"),
});

export const commentEditForm = commentForm.extend({ task_id: uuid });
export const commentDeleteForm = z.object({ task_id: uuid });

export const adminUserForm = z.object({
  role: z.enum(["admin", "member"]).optional(),
  is_active: z
    .enum(["true", "false"])
    .transform((v) => v === "true")
    .optional(),
});

/** Query-string parsing for search: anything invalid is dropped rather than rejected. */
export const searchQuery = z.object({
  q: z.string().trim().max(200).optional().catch(undefined),
  status: z.enum(TASK_STATUSES).optional().catch(undefined),
  assignee_id: uuid.optional().catch(undefined),
  label: z.string().trim().max(40).optional().catch(undefined),
  due_before: isoDate.optional().catch(undefined),
  sort: z.enum(SORT_FIELDS).optional().catch(undefined),
  order: z.enum(["asc", "desc"]).optional().catch(undefined),
  page: z.coerce.number().int().min(1).max(10_000).optional().catch(undefined),
});

export const pageQuery = z.object({
  page: z.coerce.number().int().min(1).max(10_000).catch(1).default(1),
  q: z.string().trim().max(200).optional().catch(undefined),
});

const SECRET_FIELDS = new Set([
  "password",
  "password_confirm",
  "current_password",
  "new_password",
  "new_password_confirm",
  "_csrf",
  "token",
]);

export type FormResult<T> =
  | { ok: true; data: T }
  | { ok: false; errors: Record<string, string>; values: Record<string, string> };

/** Validate a form body; on failure return messages per field and the non-secret values. */
export function parseForm<T>(schema: z.ZodType<T>, body: unknown): FormResult<T> {
  const result = schema.safeParse(body ?? {});
  if (result.success) {
    return { ok: true, data: result.data };
  }
  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = issue.path.map(String).join(".") || "form";
    errors[key] ??= issue.message;
  }
  return { ok: false, errors, values: safeValues(body) };
}

/** Echo back what the user typed, except secrets. */
export function safeValues(body: unknown): Record<string, string> {
  if (typeof body !== "object" || body === null) {
    return {};
  }
  const values: Record<string, string> = {};
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    if (typeof value === "string" && !SECRET_FIELDS.has(key)) {
      values[key] = value;
    }
  }
  return values;
}

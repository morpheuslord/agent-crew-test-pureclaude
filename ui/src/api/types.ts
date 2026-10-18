/** Shapes of the API's JSON responses (see the API's OpenAPI document). */

export type Role = "admin" | "member";
export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "low" | "medium" | "high";
export type SortField =
  | "title"
  | "description"
  | "status"
  | "priority"
  | "assignee_id"
  | "due_date"
  | "labels"
  | "created_at"
  | "updated_at";
export type SortOrder = "asc" | "desc";

export const TASK_STATUSES: readonly TaskStatus[] = ["todo", "in_progress", "done"];
export const TASK_PRIORITIES: readonly TaskPriority[] = ["low", "medium", "high"];
export const SORT_FIELDS: readonly SortField[] = [
  "created_at",
  "updated_at",
  "title",
  "description",
  "status",
  "priority",
  "assignee_id",
  "due_date",
  "labels",
];

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface LoginResult {
  token: string;
  expires_at: string;
  user: User;
}

export interface Member {
  user_id: string;
  email: string;
  display_name: string;
  is_owner: boolean;
  added_at: string;
}

export interface Team {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
}

export interface TeamDetail extends Team {
  members: Member[];
  can_manage: boolean;
}

export interface Project {
  id: string;
  team_id: string;
  name: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  team_name: string;
  can_manage: boolean;
  members: Member[];
  webhook_url: string | null;
  webhook_secret: string | null;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_id: string | null;
  assignee_name: string | null;
  due_date: string | null;
  labels: string[];
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface TaskSearchItem extends Task {
  project_name: string;
}

export interface Comment {
  id: string;
  task_id: string;
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface Attachment {
  id: string;
  task_id: string;
  uploader_id: string;
  uploader_name: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Activity {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  event_type: string;
  team_id: string;
  project_id: string | null;
  task_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface TaskQuery {
  q?: string | undefined;
  status?: TaskStatus | undefined;
  assignee_id?: string | undefined;
  label?: string | undefined;
  due_before?: string | undefined;
  sort?: SortField | undefined;
  order?: SortOrder | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
}

export interface TaskInput {
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_id: string | null;
  due_date: string | null;
  labels: string[];
}

/** A streamed file coming back from the API. */
export interface BinaryDownload {
  body: ReadableStream<Uint8Array>;
  contentType: string;
  contentDisposition: string | null;
  contentLength: string | null;
}

export interface UploadFile {
  filename: string;
  contentType: string;
  data: Buffer;
}

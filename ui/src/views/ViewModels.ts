import type {
  Activity,
  Attachment,
  Comment,
  Page,
  ProjectDetail,
  Task,
  TaskQuery,
  TaskSearchItem,
  TaskStatus,
  User,
} from "../api/types.js";
import { SORT_FIELDS, TASK_PRIORITIES, TASK_STATUSES } from "../api/types.js";
import type { MarkdownRenderer } from "./MarkdownRenderer.js";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  formatBytes,
  formatDateTime,
  queryString,
} from "./format.js";

export interface TaskCard {
  id: string;
  title: string;
  priority: string;
  assignee: string | null;
  dueDate: string | null;
  labels: string[];
}

export interface BoardColumn {
  status: TaskStatus;
  label: string;
  total: number;
  tasks: TaskCard[];
}

export interface Option {
  value: string;
  label: string;
}

const STATUS_OPTIONS: Option[] = TASK_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }));
const PRIORITY_OPTIONS: Option[] = TASK_PRIORITIES.map((p) => ({
  value: p,
  label: PRIORITY_LABELS[p],
}));

function card(task: Task): TaskCard {
  return {
    id: task.id,
    title: task.title,
    priority: PRIORITY_LABELS[task.priority],
    assignee: task.assignee_name,
    dueDate: task.due_date,
    labels: task.labels,
  };
}

function memberOptions(project: ProjectDetail): Option[] {
  return project.members.map((m) => ({ value: m.user_id, label: m.display_name }));
}

/** Project board: one column per status. */
export class BoardViewBuilder {
  build(project: ProjectDetail, pages: Record<TaskStatus, Page<Task>>) {
    const columns: BoardColumn[] = TASK_STATUSES.map((status) => ({
      status,
      label: STATUS_LABELS[status],
      total: pages[status].total,
      tasks: pages[status].items.map(card),
    }));
    return {
      project,
      columns,
      statusOptions: STATUS_OPTIONS,
      priorityOptions: PRIORITY_OPTIONS,
      memberOptions: memberOptions(project),
    };
  }
}

/** Task detail with rendered Markdown, comment permissions and attachment sizes. */
export class TaskViewBuilder {
  constructor(private readonly markdown: MarkdownRenderer) {}

  build(
    task: Task,
    project: ProjectDetail,
    comments: Comment[],
    attachments: Attachment[],
    viewer: User,
  ) {
    return {
      task,
      project,
      readOnly: project.archived,
      descriptionHtml: this.markdown.render(task.description),
      statusLabel: STATUS_LABELS[task.status],
      priorityLabel: PRIORITY_LABELS[task.priority],
      labelsText: task.labels.join(", "),
      comments: comments.map((c) => ({
        ...c,
        bodyHtml: this.markdown.render(c.body),
        createdLabel: formatDateTime(c.created_at),
        edited: c.updated_at !== c.created_at,
        canEdit: c.author_id === viewer.id && !project.archived,
      })),
      attachments: attachments.map((a) => ({
        ...a,
        sizeLabel: formatBytes(a.size_bytes),
        createdLabel: formatDateTime(a.created_at),
      })),
      statusOptions: STATUS_OPTIONS,
      priorityOptions: PRIORITY_OPTIONS,
      memberOptions: memberOptions(project),
    };
  }
}

/** Search form state, results and pagination links. */
export class SearchViewBuilder {
  build(query: TaskQuery, results: Page<TaskSearchItem> | null) {
    const base = {
      q: query.q,
      status: query.status,
      assignee_id: query.assignee_id,
      label: query.label,
      due_before: query.due_before,
      sort: query.sort,
      order: query.order,
    };
    const page = results?.page ?? 1;
    const pageSize = results?.page_size ?? 20;
    const lastPage = results ? Math.max(1, Math.ceil(results.total / pageSize)) : 1;
    return {
      query,
      results: results?.items.map((item) => ({
        ...item,
        statusLabel: STATUS_LABELS[item.status],
        priorityLabel: PRIORITY_LABELS[item.priority],
      })),
      total: results?.total ?? 0,
      page,
      lastPage,
      previousHref: page > 1 ? `/search${queryString({ ...base, page: page - 1 })}` : null,
      nextHref: page < lastPage ? `/search${queryString({ ...base, page: page + 1 })}` : null,
      statusOptions: STATUS_OPTIONS,
      sortOptions: SORT_FIELDS.map((f) => ({ value: f, label: f.replace("_", " ") })),
    };
  }
}

/** Activity feed rows with a readable summary per event type. */
export class ActivityViewBuilder {
  build(page: Page<Activity>) {
    return {
      items: page.items.map((item) => ({
        ...item,
        when: formatDateTime(item.created_at),
        summary: ActivityViewBuilder.summary(item),
      })),
      page: page.page,
      total: page.total,
      lastPage: Math.max(1, Math.ceil(page.total / page.page_size)),
    };
  }

  static summary(item: Activity): string {
    const detail = (key: string): string => {
      const value = item.details[key];
      return typeof value === "string" ? value : "";
    };
    switch (item.event_type) {
      case "task.created":
        return `created task "${detail("title")}"`;
      case "task.updated":
        return "updated a task";
      case "task.status_changed":
        return `moved a task from ${detail("old_status")} to ${detail("new_status")}`;
      case "task.deleted":
        return `deleted task "${detail("title")}"`;
      case "comment.added":
        return "commented on a task";
      case "attachment.added":
        return `attached "${detail("filename")}"`;
      case "member.added":
        return `added ${detail("display_name")} to the team`;
      case "member.removed":
        return `removed ${detail("display_name")} from the team`;
      default:
        return item.event_type;
    }
  }
}

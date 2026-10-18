import type {
  Activity,
  Attachment,
  BinaryDownload,
  Comment,
  LoginResult,
  Member,
  Page,
  Project,
  ProjectDetail,
  Role,
  Task,
  TaskInput,
  TaskQuery,
  TaskSearchItem,
  Team,
  TeamDetail,
  UploadFile,
  User,
} from "./types.js";

/** Who is calling and how to correlate the call, sent with every API request. */
export interface ApiContext {
  requestId: string;
  token?: string | undefined;
  clientIp?: string | undefined;
}

export interface ProjectChanges {
  name?: string;
  webhook_url?: string | null;
}

export interface UserChanges {
  role?: Role;
  is_active?: boolean;
}

/** Everything the UI server needs from the API. Implemented by TaskboardApiClient. */
export interface ApiClient {
  register(
    ctx: ApiContext,
    body: { email: string; display_name: string; password: string },
  ): Promise<User>;
  login(ctx: ApiContext, body: { email: string; password: string }): Promise<LoginResult>;
  logout(ctx: ApiContext): Promise<void>;
  me(ctx: ApiContext): Promise<User>;
  changePassword(
    ctx: ApiContext,
    body: { current_password: string; new_password: string },
  ): Promise<void>;
  forgotPassword(ctx: ApiContext, email: string): Promise<void>;
  resetPassword(ctx: ApiContext, body: { token: string; new_password: string }): Promise<void>;

  listTeams(ctx: ApiContext): Promise<Team[]>;
  createTeam(ctx: ApiContext, name: string): Promise<Team>;
  getTeam(ctx: ApiContext, teamId: string): Promise<TeamDetail>;
  addMember(ctx: ApiContext, teamId: string, email: string): Promise<Member>;
  removeMember(ctx: ApiContext, teamId: string, userId: string): Promise<void>;
  listTeamProjects(ctx: ApiContext, teamId: string): Promise<Project[]>;
  createProject(
    ctx: ApiContext,
    teamId: string,
    body: { name: string; webhook_url: string | null },
  ): Promise<ProjectDetail>;

  listMyProjects(ctx: ApiContext): Promise<Project[]>;
  getProject(ctx: ApiContext, projectId: string): Promise<ProjectDetail>;
  updateProject(ctx: ApiContext, projectId: string, body: ProjectChanges): Promise<ProjectDetail>;
  archiveProject(ctx: ApiContext, projectId: string): Promise<ProjectDetail>;
  listTasks(ctx: ApiContext, projectId: string, query: TaskQuery): Promise<Page<Task>>;
  createTask(ctx: ApiContext, projectId: string, body: TaskInput): Promise<Task>;
  exportCsv(ctx: ApiContext, projectId: string): Promise<BinaryDownload>;
  projectActivity(ctx: ApiContext, projectId: string, page: number): Promise<Page<Activity>>;

  getTask(ctx: ApiContext, taskId: string): Promise<Task>;
  updateTask(ctx: ApiContext, taskId: string, body: Partial<TaskInput>): Promise<Task>;
  deleteTask(ctx: ApiContext, taskId: string): Promise<void>;
  listComments(ctx: ApiContext, taskId: string): Promise<Comment[]>;
  addComment(ctx: ApiContext, taskId: string, body: string): Promise<Comment>;
  updateComment(ctx: ApiContext, commentId: string, body: string): Promise<Comment>;
  deleteComment(ctx: ApiContext, commentId: string): Promise<void>;
  listAttachments(ctx: ApiContext, taskId: string): Promise<Attachment[]>;
  uploadAttachment(ctx: ApiContext, taskId: string, file: UploadFile): Promise<Attachment>;
  downloadAttachment(ctx: ApiContext, attachmentId: string): Promise<BinaryDownload>;

  searchTasks(ctx: ApiContext, query: TaskQuery): Promise<Page<TaskSearchItem>>;

  listUsers(ctx: ApiContext, query: { q?: string | undefined; page: number }): Promise<Page<User>>;
  updateUser(ctx: ApiContext, userId: string, body: UserChanges): Promise<User>;
  globalActivity(ctx: ApiContext, page: number): Promise<Page<Activity>>;

  /** True when the API answers its readiness probe. */
  ready(requestId: string): Promise<boolean>;
}

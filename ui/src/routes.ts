import { Router } from "express";
import type { AuthController } from "./controllers/AuthController.js";
import type {
  AdminController,
  ProfileController,
  SearchController,
} from "./controllers/AccountControllers.js";
import type { DashboardController } from "./controllers/DashboardController.js";
import type { ProjectController } from "./controllers/ProjectController.js";
import type { TaskController } from "./controllers/TaskController.js";
import type { TeamController } from "./controllers/TeamController.js";
import type { Guards } from "./middleware/Guards.js";

export interface Controllers {
  auth: AuthController;
  dashboard: DashboardController;
  teams: TeamController;
  projects: ProjectController;
  tasks: TaskController;
  search: SearchController;
  profile: ProfileController;
  admin: AdminController;
}

const ID_PARAMS = ["teamId", "userId", "projectId", "taskId", "commentId", "attachmentId"];

/** Every page route. All POSTs are form submissions that end in a redirect (PRG). */
export function buildRouter(c: Controllers, guards: Guards): Router {
  const router = Router();
  for (const name of ID_PARAMS) {
    router.param(name, guards.uuidParam);
  }

  router.get("/login", c.auth.showLogin);
  router.post("/login", c.auth.login);
  router.get("/register", c.auth.showRegister);
  router.post("/register", c.auth.register);
  router.get("/forgot-password", c.auth.showForgot);
  router.post("/forgot-password", c.auth.forgot);
  router.get("/reset-password", c.auth.showReset);
  router.post("/reset-password", c.auth.reset);
  router.post("/logout", c.auth.logout);

  const auth = guards.requireAuth;
  router.get("/", auth, c.dashboard.show);
  router.post("/teams", auth, c.dashboard.createTeam);

  router.get("/teams/:teamId", auth, c.teams.show);
  router.post("/teams/:teamId/members", auth, c.teams.addMember);
  router.post("/teams/:teamId/members/:userId/remove", auth, c.teams.removeMember);
  router.post("/teams/:teamId/projects", auth, c.teams.createProject);

  router.get("/projects/:projectId", auth, c.projects.show);
  router.post("/projects/:projectId/tasks", auth, c.projects.createTask);
  router.post("/projects/:projectId/settings", auth, c.projects.updateSettings);
  router.post("/projects/:projectId/archive", auth, c.projects.archive);
  router.get("/projects/:projectId/export.csv", auth, c.projects.exportCsv);
  router.get("/projects/:projectId/activity", auth, c.projects.activity);

  router.get("/tasks/:taskId", auth, c.tasks.show);
  router.post("/tasks/:taskId", auth, c.tasks.update);
  router.post("/tasks/:taskId/status", auth, c.tasks.setStatus);
  router.post("/tasks/:taskId/delete", auth, c.tasks.remove);
  router.post("/tasks/:taskId/comments", auth, c.tasks.addComment);
  router.post("/tasks/:taskId/attachments", auth, c.tasks.upload);
  router.post("/comments/:commentId", auth, c.tasks.editComment);
  router.post("/comments/:commentId/delete", auth, c.tasks.deleteComment);
  router.get("/attachments/:attachmentId/download", auth, c.tasks.download);

  router.get("/search", auth, c.search.show);
  router.get("/profile", auth, c.profile.show);
  router.post("/profile/password", auth, c.profile.changePassword);

  const admin = [auth, guards.requireAdmin];
  router.get("/admin/users", ...admin, c.admin.users);
  router.post("/admin/users/:userId", ...admin, c.admin.updateUser);
  router.get("/admin/activity", ...admin, c.admin.activity);
  return router;
}

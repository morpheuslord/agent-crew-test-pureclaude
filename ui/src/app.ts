import { fileURLToPath } from "node:url";
import cookieParser from "cookie-parser";
import express, { type Express } from "express";
import type { Logger } from "pino";
import type { ApiClient } from "./api/ApiClient.js";
import type { AppConfig } from "./config.js";
import {
  AdminController,
  HealthController,
  ProfileController,
  SearchController,
} from "./controllers/AccountControllers.js";
import { AuthController } from "./controllers/AuthController.js";
import { DashboardController } from "./controllers/DashboardController.js";
import { ProjectController } from "./controllers/ProjectController.js";
import { TaskController } from "./controllers/TaskController.js";
import { TeamController } from "./controllers/TeamController.js";
import { CsrfProtection } from "./middleware/CsrfProtection.js";
import { ErrorHandler } from "./middleware/ErrorHandler.js";
import { FlashMessages } from "./middleware/FlashMessages.js";
import { Guards } from "./middleware/Guards.js";
import { RequestContextMiddleware } from "./middleware/RequestContextMiddleware.js";
import { SecurityHeaders } from "./middleware/SecurityHeaders.js";
import { SessionMiddleware } from "./middleware/SessionMiddleware.js";
import { UploadGate } from "./middleware/UploadGate.js";
import { buildRouter } from "./routes.js";
import { MarkdownRenderer } from "./views/MarkdownRenderer.js";
import {
  ActivityViewBuilder,
  BoardViewBuilder,
  SearchViewBuilder,
  TaskViewBuilder,
} from "./views/ViewModels.js";

export interface AppDependencies {
  config: AppConfig;
  logger: Logger;
  api: ApiClient;
}

const VIEWS_DIR = fileURLToPath(new URL("../views", import.meta.url));
const PUBLIC_DIR = fileURLToPath(new URL("../public", import.meta.url));

/** Build the Express application around an API client. */
export function createApp({ config, logger, api }: AppDependencies): Express {
  const app = express();
  app.disable("x-powered-by");
  app.set("trust proxy", config.trustProxy);
  app.set("view engine", "ejs");
  app.set("views", VIEWS_DIR);

  const flash = new FlashMessages(config.cookieSecure);
  const session = new SessionMiddleware(api, config.cookieSecure);
  const csrf = new CsrfProtection(config.uiSecret, config.publicOrigin, config.cookieSecure);
  const security = new SecurityHeaders(config.cookieSecure);
  const guards = new Guards();
  const errors = new ErrorHandler(logger, session);
  const health = new HealthController(api);
  const activity = new ActivityViewBuilder();

  app.use(new RequestContextMiddleware(logger).handle);
  app.use(security.headers);
  app.use("/static", express.static(PUBLIC_DIR, { index: false, maxAge: "1h" }));
  app.get("/healthz", health.healthz);
  app.get("/readyz", health.readyz);

  app.use(security.noStore);
  app.use(cookieParser(config.uiSecret));
  app.use(express.urlencoded({ extended: false, limit: "64kb", parameterLimit: 50 }));
  app.use(new UploadGate(config.maxUploadBytes).handle);
  app.use(csrf.issue);
  app.use(csrf.verify);
  app.use(flash.consume);
  app.use(session.load);

  app.use(
    buildRouter(
      {
        auth: new AuthController(api, flash, session, csrf),
        dashboard: new DashboardController(api, flash),
        teams: new TeamController(api, flash),
        projects: new ProjectController(api, flash, new BoardViewBuilder(), activity),
        tasks: new TaskController(api, flash, new TaskViewBuilder(new MarkdownRenderer())),
        search: new SearchController(api, flash, new SearchViewBuilder()),
        profile: new ProfileController(api, flash),
        admin: new AdminController(api, flash, activity),
      },
      guards,
    ),
  );
  app.use(errors.notFound);
  app.use(errors.handle);
  return app;
}

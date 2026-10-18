import type { Request, Response } from "express";
import { parseForm, teamForm } from "../forms.js";
import { BaseController } from "./BaseController.js";

/** The signed-in home page: my teams, my projects, tasks assigned to me. */
export class DashboardController extends BaseController {
  readonly show = async (req: Request, res: Response): Promise<void> => {
    const ctx = this.ctx(req, res);
    const user = this.user(res);
    const [teams, projects, assigned] = await Promise.all([
      this.api.listTeams(ctx),
      this.api.listMyProjects(ctx),
      this.api.searchTasks(ctx, {
        assignee_id: user.id,
        sort: "due_date",
        order: "asc",
        page_size: 20,
      }),
    ]);
    res.render("dashboard", { teams, projects, assigned: assigned.items, errors: {}, values: {} });
  };

  readonly createTeam = async (req: Request, res: Response): Promise<void> => {
    const form = parseForm(teamForm, req.body);
    if (!form.ok) {
      this.flash.error(res, `Team name: ${form.errors.name ?? "invalid"}`);
      res.redirect(303, "/");
      return;
    }
    let teamId = "";
    const ok = await this.attempt(res, async () => {
      teamId = (await this.api.createTeam(this.ctx(req, res), form.data.name)).id;
    });
    if (ok) {
      this.flash.success(res, "Team created.");
      res.redirect(303, `/teams/${teamId}`);
      return;
    }
    res.redirect(303, "/");
  };
}

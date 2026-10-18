import type { Request, Response } from "express";
import { memberForm, parseForm, projectForm } from "../forms.js";
import { BaseController } from "./BaseController.js";

/** Team page: members and projects. */
export class TeamController extends BaseController {
  readonly show = async (req: Request, res: Response): Promise<void> => {
    const ctx = this.ctx(req, res);
    const teamId = this.param(req, "teamId");
    const [team, projects] = await Promise.all([
      this.api.getTeam(ctx, teamId),
      this.api.listTeamProjects(ctx, teamId),
    ]);
    res.render("team", { team, projects });
  };

  readonly addMember = async (req: Request, res: Response): Promise<void> => {
    const teamId = this.param(req, "teamId");
    const form = parseForm(memberForm, req.body);
    if (!form.ok) {
      this.flash.error(res, "Enter a valid email address.");
    } else if (
      await this.attempt(res, () => this.api.addMember(this.ctx(req, res), teamId, form.data.email))
    ) {
      this.flash.success(res, "Member added.");
    }
    res.redirect(303, `/teams/${teamId}`);
  };

  readonly removeMember = async (req: Request, res: Response): Promise<void> => {
    const teamId = this.param(req, "teamId");
    const userId = this.param(req, "userId");
    if (await this.attempt(res, () => this.api.removeMember(this.ctx(req, res), teamId, userId))) {
      this.flash.success(res, "Member removed.");
    }
    res.redirect(303, `/teams/${teamId}`);
  };

  readonly createProject = async (req: Request, res: Response): Promise<void> => {
    const teamId = this.param(req, "teamId");
    const form = parseForm(projectForm, req.body);
    if (!form.ok) {
      this.flash.error(res, Object.values(form.errors).join(" "));
      res.redirect(303, `/teams/${teamId}`);
      return;
    }
    let projectId = "";
    const ok = await this.attempt(res, async () => {
      projectId = (await this.api.createProject(this.ctx(req, res), teamId, form.data)).id;
    });
    if (ok) {
      this.flash.success(res, "Project created.");
      res.redirect(303, `/projects/${projectId}`);
      return;
    }
    res.redirect(303, `/teams/${teamId}`);
  };
}

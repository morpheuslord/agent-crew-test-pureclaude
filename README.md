# Taskboard

Taskboard is a small internal task tracker for teams. People sign up, create teams, add teammates,
create projects inside a team and manage tasks with Markdown descriptions, comments and file
attachments. Admins manage users and can see all activity.

It has two services:

- **API** (`api/`): Python 3.13, FastAPI, SQLAlchemy 2, Alembic. Owns all data and business rules,
  talks to PostgreSQL 16, Redis 7 (cache and rate limits) and attachment storage (local volume or S3).
- **UI server** (`ui/`): Node.js 24, Express 5, EJS, TypeScript. Renders the pages, holds the browser
  session cookie and calls the API over the internal network. The browser never talks to the API.

```
Browser --HTTPS--> ALB --> UI server --internal network--> API --> PostgreSQL
                                                              |--> Redis
                                                              |--> attachments (volume / S3)
```

Infrastructure for AWS (VPC, ALB, EC2, RDS, ElastiCache, S3, ECR, IAM) is in `infra/` as Terraform.

## Documentation

| Document | Contents |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, request flow, authentication, authorisation, data model, caching, API contract |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Terraform layout and how a deployment works end to end |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Design decisions with reasons |
| `evaluation/` | Build evaluation record (tool log, security findings) |

The API's OpenAPI document is served internally at `/api/v1/openapi.json`.

## Run it locally with Docker Compose

Requirements: Docker with Compose v2.

```bash
cp .env.example .env
# Replace every change-me value, e.g. with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
make up        # docker compose up --build -d
make admin     # create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD in .env
make smoke     # end-to-end check through the UI
```

Open <http://localhost:3000>. Only the UI is published, and only on `127.0.0.1`; the API, PostgreSQL
and Redis are reachable on the internal Compose networks only.

There is no email provider. Password reset emails are written to the `outbox` table and, with
`MAILER_LOG_BODY=true` (the dev default), to the API log:

```bash
docker compose logs api | grep "email written to outbox"
```

`make down` stops the stack; `docker compose down -v` also deletes the data volumes.

## Develop without containers

Requirements: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node.js 24 with npm, PostgreSQL 16,
Redis 7, Terraform 1.11 or newer.

```bash
make install                      # uv sync --frozen, npm ci

# API on :8000 (see .env.example for every variable)
cd api
export DATABASE_URL=postgresql+psycopg://taskboard:secret@localhost:5432/taskboard
export REDIS_URL=redis://localhost:6379/0 SERVICE_TOKEN=... PUBLIC_UI_URL=http://localhost:3000
export STORAGE_LOCAL_PATH=./var/attachments
uv run taskboard-api migrate
uv run taskboard-api serve

# UI on :3000
cd ui
export API_BASE_URL=http://localhost:8000 SERVICE_TOKEN=... UI_SECRET=... \
       PUBLIC_URL=http://localhost:3000 COOKIE_SECURE=false
npm run dev
```

## Checks

| Command | What it runs |
| --- | --- |
| `make fmt` | ruff format and fix, prettier, terraform fmt |
| `make lint` | `ruff check`, `ruff format --check`, `eslint`, `prettier --check` |
| `make typecheck` | `mypy --strict`, `tsc --noEmit` |
| `make test` | API unit and integration tests (coverage at least 80%), UI Vitest/Supertest tests (coverage at least 80%) |
| `make tf-check` | `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate` |
| `make smoke` | `scripts/smoke.sh` against the running stack, through the UI only |

The API integration tests need a PostgreSQL database and a Redis database they may wipe:

```bash
make test-services     # PostgreSQL and Redis on 127.0.0.1:55432 / :56379 (docker-compose.test.yml)
make test
make test-services-down
```

or point `TEST_DATABASE_URL` and `TEST_REDIS_URL` at your own instances. Without them the integration
tests are skipped and the coverage threshold fails.

CI (`.github/workflows/ci.yml`) runs the same lint, type and test steps with PostgreSQL and Redis
service containers, the Terraform checks, and builds both images. CodeQL, Codacy, Semgrep and Trivy
run in their own workflows.

## Repository layout

```
api/            Python API (src/taskboard_api: api, services, repositories, models, cache, ...)
ui/             Node.js UI server (src: api client, controllers, middleware, views; views/: EJS)
infra/          Terraform: modules/ and envs/dev/
scripts/        smoke.sh
docs/           architecture, deployment, decisions
evaluation/     evaluation record of this build
```

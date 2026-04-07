---
name: devops
description: Owns Docker Compose, Grafana provisioning, Caddy config, GitHub Actions workflows, and deployment. Responsible for all infrastructure and CI/CD changes.
---

# DevOps Engineer

You own infrastructure for the recommendator project — everything that makes the code run, including CI/CD pipelines.

## Skills to Reference

- `docker-compose-patterns` — service definitions, healthchecks, networks, volumes
- `grafana-provisioning` — datasource + dashboard-as-code

## Deployment Stages

### Stage A — Local development (current)
- Docker Compose on developer machine
- All services in one Compose file
- Hot-reload for backend (`uvicorn --reload`)
- No TLS needed locally

### Stage B — DigitalOcean single Droplet (Phase 3+)
- Same Docker Compose, single Droplet
- Caddy as reverse proxy with automatic TLS
- Managed PostgreSQL (separate from app Droplet)
- Secrets via `.env` file, never committed

### Stage C — DOKS (when justified by real load)
- Only when ingest, scoring, and API need independent scaling
- Or when multi-tenancy requires isolation

## Services Inventory

| Service | Image | Purpose |
|---|---|---|
| `db` | `postgres:16` | Primary datastore |
| `api` | `./backend` (api entry) | FastAPI REST |
| `worker` | `./backend` (worker entry) | Factor computation jobs |
| `scheduler` | `./backend` (scheduler entry) | Job dispatch |
| `grafana` | `grafana/grafana-oss:10.4+` | Internal dashboards |
| `caddy` | `caddy:latest` | Reverse proxy + TLS |
| `redis` | `redis:7-alpine` | Add only when needed |

## Infrastructure Rules

1. **Healthchecks on all stateful services** — `db`, `redis` (if added)
2. **Named volumes** — never anonymous volumes for persistent data
3. **Two networks** — `front-tier` (caddy ↔ api, caddy ↔ grafana), `back-tier` (api ↔ db, worker ↔ db)
4. **Grafana provisioned as code** — datasources and dashboards as YAML/JSON in `services/grafana/provisioning/`, never manual click-ops
5. **Secrets in `.env`** — `.env.example` committed, `.env` in `.gitignore`
6. **Single backend image** — api, worker, and scheduler use the same built image with different `command:` overrides
7. **`docker compose up`** must work from a clean clone with only `.env` filled in

## Grafana Dashboard Groups

Provision four dashboard folders:
1. **Pipeline** — ingest run status, API errors, stale data warnings, missing fields
2. **Market** — top gainers by composite score, relative strength heatmap, unusual volume, sector momentum
3. **Fundamentals** — revenue/EPS acceleration, margin expansion, ROE/ROIC/debt/FCF
4. **Alerts** — new breakouts, insider-buy signals, estimate revision changes, watchlist triggers

## GitHub Actions Workflows

Workflows live in `.github/workflows/`. Own and maintain all of them.

### Workflow inventory by phase

| Workflow | File | Created in | Trigger |
|---|---|---|---|
| CI — test + lint | `ci.yml` | Phase 1 | push, PR to main |
| Docker build check | `docker-build.yml` | Phase 1 | push, PR to main |
| CD — deploy to Droplet | `deploy.yml` | Phase 3 | push to main (after merge) |

### `ci.yml` (Phase 1 — create immediately)

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: stocks_test
          POSTGRES_USER: stocks
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r backend/requirements.txt -r requirements-dev.txt
      - run: ruff check backend/
      - run: pytest tests/ -q
        env:
          DATABASE_URL: postgresql://stocks:test@localhost:5432/stocks_test
```

### `docker-build.yml` (Phase 1 — create immediately)

```yaml
name: Docker build
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: docker build ./backend --target prod
```

### `deploy.yml` (Phase 3 — create when Droplet is provisioned)

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Droplet via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DROPLET_HOST }}
          username: ${{ secrets.DROPLET_USER }}
          key: ${{ secrets.DROPLET_SSH_KEY }}
          script: |
            cd /opt/recommendator
            git pull origin main
            docker compose pull
            docker compose up -d --build
            docker compose exec -T db psql -U stocks -d stocks -f /migrations/latest.sql
```

### GHA Rules

- CI must pass before any merge to `main`
- Secrets (API keys, SSH keys, Droplet IP) stored in GitHub repository secrets — never in workflow YAML
- Do not add CD pipeline before Stage B deployment is set up (Phase 3)
- Keep workflows fast — cache pip dependencies, run lint before tests to fail early

## Makefile Targets

Maintain these targets:
```
make up       — build + start all services
make down     — stop and remove containers
make logs     — follow all service logs
make migrate  — run DB migrations
make seed     — insert initial ticker list
make test     — run pytest inside backend container
make shell    — open psql in db container
```

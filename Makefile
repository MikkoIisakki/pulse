.PHONY: up down logs migrate seed test lint typecheck fresh shell-db

## Build and start all services
up:
	docker compose up --build -d

## Stop and remove containers
down:
	docker compose down

## Follow all service logs
logs:
	docker compose logs -f

## Apply all migrations in order
migrate:
	@for f in db/migrations/*.sql; do \
		echo "Applying $$f"; \
		docker compose exec -T db psql -U $${DB_USER:-stocks} -d $${DB_NAME:-stocks} -f "/dev/stdin" < "$$f"; \
	done

## Apply all seed files in order
seed:
	@for f in db/seeds/*.sql; do \
		echo "Seeding $$f"; \
		docker compose exec -T db psql -U $${DB_USER:-stocks} -d $${DB_NAME:-stocks} -f "/dev/stdin" < "$$f"; \
	done

## Run tests with coverage
test:
	docker compose run --rm api pytest tests/ -q

## Run linter
lint:
	docker compose run --rm api ruff check backend/app/

## Run type checker
typecheck:
	docker compose run --rm api mypy backend/app/

## Open a psql shell in the db container
shell-db:
	docker compose exec db psql -U $${DB_USER:-stocks} -d $${DB_NAME:-stocks}

## Nuclear reset: wipe everything and start fresh
fresh: down
	docker compose down -v
	$(MAKE) up
	@echo "Waiting for db to be healthy..."
	@sleep 5
	$(MAKE) migrate
	$(MAKE) seed

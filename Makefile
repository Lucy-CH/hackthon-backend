.PHONY: dev db-migrate db-upgrade db-downgrade

dev:
	uv run fastapi dev app/main.py

db-migrate:
	uv run alembic revision --autogenerate

db-upgrade:
	uv run alembic upgrade head

db-downgrade:
	uv run alembic downgrade -1
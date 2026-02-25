PYTHON = uv run python
MANAGE = $(PYTHON) manage.py

# Default target
.DEFAULT_GOAL := help

## Show available commands
help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make dev            - Run Django development server"
	@echo "  make shell          - Open Django shell"
	@echo "  make migrate        - Apply migrations"
	@echo "  make makemigrations - Create new migrations"
	@echo "  make superuser      - Create Django superuser"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run flake8 linting"
	@echo "  make format         - Format code with Black and isort"
	@echo "  make clean          - Remove pyc files and caches"

## Install dependencies
install:
	uv pip install -r requirements.txt

## Run development server
dev:
	$(MANAGE) runserver

## Open Django shell
shell:
	$(MANAGE) shell

## Apply migrations
migrate:
	$(MANAGE) migrate

## Create migrations
makemigrations:
	$(MANAGE) makemigrations

## Create superuser
superuser:
	$(MANAGE) createsuperuser

## Run tests
test:
	$(MANAGE) test

## Lint code
lint:
	uv run flake8 .

## Format code to standard (Black + isort)
format:
	uv run isort .
	uv run black .

## Clean up cache and pyc files
clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete

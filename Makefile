ifneq (,$(wildcard ./.env))
include .env
export 
ENV_FILE_PARAM = --env-file .env

endif

build:
	docker compose up --build -d --remove-orphans

up_build:
	docker compose -f docker-compose.dev.yml up --build 

up:
	docker compose up 

up_d:
	docker compose up -d

up_f:
	docker compose -f docker-compose.dev.yml up 

down:
	docker compose down

down_f:
	docker compose -f docker-compose.dev.yml down

show_logs:
	docker compose logs

serv:
	uvicorn src.main:app --reload

create_env:
	python3.12 -m venv venv

reqn:
	pip install -r requirements/dev.txt

ureqn:
	pip freeze > requirements/dev.txt

alembic_init:
	alembic init -t async migrations

mmig: 
	if [ -z "$(message)" ]; then \
		alembic revision --autogenerate; \
	else \
		alembic revision --autogenerate -m "$(message)"; \
	fi

mmig_auto:
	alembic revision --autogenerate
	
mig:
	alembic upgrade head

tests:
	pytest --disable-warnings -vv -x -s

mjml:
	bash scripts/build-mjml.sh

random_s:
	python3 -c "import secrets; print(secrets.token_urlsafe(32))"

ngrok:
	ngrok http 7000

celery:
	celery -A src.app_name.celery_config.celery_app worker --loglevel=info --concurrency=3

celery-beat:
	celery -A src.app_name.celery_config.celery_app beat --loglevel=info

redis:
	docker run --name redis -p 6379:6379 redis

redis_d:
	docker run -d --name redis -p 6379:6379 redis

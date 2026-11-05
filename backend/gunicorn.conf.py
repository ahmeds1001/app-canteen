"""gunicorn settings for the backend container (docker-compose.yml). Values can be tuned in .env without a rebuild.

gthread workers: each worker serves GUNICORN_THREADS requests at once, so one waiting on SQL Server or on a password
check (Argon2, ~100 MB and a fraction of a second each) does not hold the others. Size: workers x threads concurrent
requests; memory about 150 MB per worker + 100 MB per login in progress (fits the 2 GB limit with 4 x 2).
"""
import os

bind = "0.0.0.0:8000"
worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS", "4"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = 60  # a request taking longer is stuck: the worker is replaced
graceful_timeout = 30
max_requests = 2000  # recycle workers now and then (memory hygiene), at random moments
max_requests_jitter = 200
accesslog = "-"  # one line per request in `docker compose logs backend`

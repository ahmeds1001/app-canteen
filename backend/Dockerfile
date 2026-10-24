FROM python:3.12-slim

# Microsoft ODBC Driver 18 for SQL Server
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
 && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/base.txt
COPY . .
ENV DJANGO_SETTINGS_MODULE=config.settings.prod PYTHONUNBUFFERED=1
RUN DJANGO_SECRET_KEY=build-only DB_ENGINE=sqlite python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]

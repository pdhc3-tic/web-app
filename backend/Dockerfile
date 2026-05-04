FROM python:3.12-slim

WORKDIR /app

# Evita gerar .pyc e melhora logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copia apenas dependências primeiro (melhora cache)
COPY requirements/base.txt /app/requirements/base.txt

RUN pip install --no-cache-dir -r /app/requirements/base.txt

COPY . /app

# Expor porta
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
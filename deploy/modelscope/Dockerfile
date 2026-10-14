FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
WORKDIR /app
COPY backend/requirements*.txt /app/backend/
RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ -r /app/backend/requirements.txt -c /app/backend/requirements-lock.txt
RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . /app
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 7860
CMD ["python", "app.py"]

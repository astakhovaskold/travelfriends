FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend
WORKDIR /app
COPY backend/requirements.txt backend/requirements-dev.txt /app/backend/
RUN pip install --no-cache-dir -r backend/requirements-dev.txt
RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser backend /app/backend
COPY --chown=appuser:appuser frontend /app/frontend
COPY --chown=appuser:appuser pytest.ini /app/pytest.ini
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

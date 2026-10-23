# ==============================================================================
# Stage 1: Build the React Frontend (Node.js)
# ==============================================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Production Runtime (Python + FastAPI)
# ==============================================================================
FROM python:3.12-slim AS runner
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source, runner, and district boundaries
COPY backend/src ./src
COPY backend/scripts ./scripts
COPY backend/run.py ./
COPY frontend/src/data/boundaries ./boundaries

# Copy the compiled React dashboard from Stage 1 into the location expected by FastAPI
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose FastAPI application port
EXPOSE 8000

# Start server
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]

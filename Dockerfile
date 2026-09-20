FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY backend ./backend
COPY frontend ./frontend

# Create data directory for SQLite
RUN mkdir -p data

# Expose port
EXPOSE 8000

# Run FastAPI app with Uvicorn
CMD ["sh", "-c", "python -m backend.main"]

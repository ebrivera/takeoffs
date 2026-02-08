FROM python:3.11-slim

WORKDIR /app

# System deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY . .

# Install the package in dev mode
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "cantena.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

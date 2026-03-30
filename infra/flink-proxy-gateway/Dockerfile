# Flink Gateway Proxy Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
# Copy README.md
COPY README.md ./

# Install dependencies using pip instead of uv to avoid freezing on macOS/Debian network edge cases
RUN pip install --no-cache-dir --default-timeout=1000 -e .

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

# Run the application
CMD ["python", "-m", "uvicorn", "flink_gateway_proxy.main:app", "--host", "0.0.0.0", "--port", "8080"]

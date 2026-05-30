FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source — exclude tests and local venv
COPY agent ./agent
COPY core ./core
COPY schemas ./schemas
COPY tools ./tools
COPY data ./data
COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

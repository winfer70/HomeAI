# Build context is the heimdall/ directory (see docker-compose.memory.yml),
# so this can COPY both poller/ and scripts/ - the poller script lives
# alongside Heimdall's other operational scripts, not duplicated here.
FROM python:3.12-slim

WORKDIR /app

COPY poller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/memory_poller.py .

CMD ["python", "memory_poller.py"]

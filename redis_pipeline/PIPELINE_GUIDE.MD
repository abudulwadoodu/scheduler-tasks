# Data Extraction Pipeline — Documentation

## Overview

This pipeline scrapes and extracts structured data from URLs on a scheduled basis. It uses **Redis Streams** for message passing between components, **MS SQL Server** as the primary database, and a modular **Python extractor** system that routes work across parallel workers.

---

## Architecture

```
Database (SQL Server)
        │
        ▼
 scheduler_agent.py        ← polls DB for due items, dispatches to Redis
        │
        ▼
  Redis Streams             ← urls1, urls2, ... urlsN (one per extractor replica)
        │
        ▼
 extractor.launcher         ← spawns N extractor workers
        │
        ▼
 extractor.worker (×N)      ← reads stream, runs domain extractor, writes to "extracted"
        │
        ▼
  Redis Stream: "extracted" ← consumed by downstream agents
        │
     ┌──┴──────────────────┐
     ▼                     ▼
validator_agent.py    logger_agent.py
                           │
                      retry_scheduler.py  ← retries failed URLs from sorted set
```

---

## Components

### `scheduler_agent.py`
Polls the SQL Server database at a configurable interval for items that are due to run. For each due item it:
- Determines the correct Redis stream using **domain-affinity routing** (same domain always goes to the same stream) with **least-loaded stream** as the fallback for new domains.
- Pushes the item payload (URL, job ID, item metadata, script path, etc.) onto the chosen stream.
- Uses `APScheduler` in background mode to keep running at the configured interval.

**Key config:**
| Setting | Source |
|---|---|
| Polling interval | `scheduler_core/config.py → Config.INTERVAL_SECONDS` |
| Batch size | `scheduler_core/config.py → Config.BATCH_SIZE` |
| Number of streams | `config.yml → pipeline.extractor.replicas` |
| Stream prefix | `config.yml → pipeline.extractor.stream_prefix` |

---

### `extractor/launcher.py`
Entry point to start all extractor workers. Reads `replicas` from config and spawns that many subprocesses, each with its own `STREAM_NAME` and `CONSUMER_NAME` environment variable set.

Run with:
```bash
python -m extractor.launcher
```

---

### `extractor/worker.py`
The core extraction worker. Each instance:
1. Joins a Redis consumer group on its assigned stream.
2. On startup, **drains any pending (unacknowledged) messages first** — crash recovery.
3. Reads new messages in a blocking loop.
4. Resolves a domain-specific extractor module from `extractors/<domain>.py`.
5. Runs the extractor and writes results to the `extracted` stream.
6. On failure, retries once immediately; on second failure, schedules the URL into the `failed_urls` sorted set (score = Unix timestamp 60 s in the future).
7. ACKs every message exactly once after processing.

**Extractor module resolution:**
- Domain `www.example.com` → module `extractors.example_com`
- If no module exists, the message is forwarded to `extracted` with `error: Extractor not found`.

---

### `validator_agent.py`
Consumes from the `extracted` stream and validates the data returned by extractors. (Connect your validation logic here.)

---

### `logger_agent.py`
Consumes from the `extracted` stream and persists job status and results to the database. Uses `log_job_update()` to record `extracted_done`, `extracted_success`, and `extracted_failed` counters on each job hash in Redis.

---

### `retry_scheduler.py`
Periodically checks the `failed_urls` sorted set for URLs whose retry timestamp has passed, and re-enqueues them into the appropriate Redis stream.

---

## Setup Guide

### 1. Redis

Pull and start a Redis container:
```bash
docker pull redis
docker run -d -p 6379:6379 --name redis redis
```

Optionally start **RedisInsight** (web UI at `http://localhost:5540`):
```bash
docker pull redis/redisinsight:latest
docker run -d --name redisinsight -p 5540:5540 redis/redisinsight:latest
```

Access the Redis CLI:
```bash
docker exec -it redis redis-cli
```

---

### 2. Database (MS SQL Server)

1. Install **SQL Server 2022**.
2. Create a server instance named `MSSQLSERVER02` on `localhost`.
3. Create a database named `gor_data_extraction`.
4. Update the connection string in both `settings.yaml` and `config.yml`:

```yaml
database:
  url: "mssql+pyodbc:///?odbc_connect=Server=localhost\MSSQLSERVER02;Database=gor_data_extraction;Trusted_Connection=Yes;driver=ODBC+Driver+18+for+SQL+Server;Encrypt=yes;TrustServerCertificate=yes"
```

5. Populate test data:
```bash
python data_import/import_data.py <file_path>
```

---

### 3. Configuration (`config.yml`)

```yaml
pipeline:
  extractor:
    replicas: 1          # number of parallel extractor workers
    stream_prefix: urls  # streams will be urls1, urls2, ...
    group: extractors    # Redis consumer group name

redis:
  host: localhost
  port: 6379

database:
  url: "mssql+pyodbc:///?odbc_connect=..."
```

---

### 4. Starting the Pipeline

Run each component in a separate terminal (or process manager):

```bash
# 1. Start extractor workers (all replicas)
python -m extractor.launcher

# 2. Start the scheduler (polls DB and dispatches to Redis)
python scheduler_agent.py

# 3. Start the validator
python validator_agent.py

# 4. Start the logger
python logger_agent.py

# 5. Start the retry handler
python retry_scheduler.py
```

---

## Adding a New Extractor

1. Identify the domain (e.g., `prices.example.com`).
2. Create `extractors/prices_example_com.py`.
3. Implement a single `extract(url: str) -> dict` function that returns a flat dictionary of string-serialisable values.

```python
# extractors/prices_example_com.py

def extract(url: str) -> dict:
    # your scraping logic here
    return {
        "price": "99.99",
        "currency": "USD",
        "title": "Product Name",
    }
```

No registration needed — the worker resolves the module name automatically from the URL domain.

---

## Redis Key Reference

| Key | Type | Purpose |
|---|---|---|
| `urls1`, `urls2`, … | Stream | Work queues for extractor workers |
| `extracted` | Stream | Output queue (validated, logged) |
| `failed_urls` | Sorted Set | URLs scheduled for retry (score = retry Unix time) |
| `job:<id>` | Hash | Job status, timestamps, counters |
| `domain_to_stream` | Hash | Domain → stream affinity map |
| `stream_rr_counter` | String | Round-robin counter (fallback routing) |

---

## Fault Tolerance

- **Worker crash recovery:** On restart, the worker reads `id=0` (pending messages) before pulling new ones. Any unacknowledged message from a crashed session is reprocessed.
- **Extractor errors:** One automatic inline retry. On second failure the URL is placed in `failed_urls` with a 60-second delay before `retry_scheduler.py` re-enqueues it.
- **Missing extractor:** Gracefully logged and forwarded downstream with an error field — the pipeline does not stall.
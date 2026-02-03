# Scheduler Tasks

A robust task scheduler with advanced resuming logic, dynamic script mapping, and multi-source extraction support.

## Features

- **Interval & RRULE Scheduling**: Support for simple interval-based tasks and complex recurrence rules (Minutely, Weekly, Monthly).
- **Resume Logic**: Checkpointed execution using task status to resume interrupted jobs from the last successful item.
- **Case-Insensitive Script Mapping**: Semi-automated association of items to extraction scripts based on manually entered `source_id` and `item_type`, with case-insensitive source lookup.
- **Manual Source Management**: Full user control over the `sources` table; scripts are only registered for pre-existing sources.

## Project Structure

- `/app`: Core logic, models, and database configuration.
- `/extractor_modules`: Storage for source-specific extraction scripts (e.g., `amazon_type_1.py`).
- `/scripts`: Utility scripts for database management and verification.
- `/tests`: Automated tests for recurrence logic and scheduler behavior.

## Getting Started

### 1. Installation
Install the required dependencies:
```bash
pip install -r requirements.txt
```

### 2. Database Setup
Initialize the database and apply the latest migrations:
```bash
python scripts/migrate_db.py
```

### 3. Seed Data & Mapping
Populate the database with test schedules and map scripts to items:
```bash
$env:PYTHONPATH = "."; python scripts/seed_data.py
$env:PYTHONPATH = "."; python scripts/populate_mappings.py
```

### 4. Running the Scheduler
Start the background scheduler:
```bash
python main.py
```

## Verification Utilities

- **Check Mappings**: `$env:PYTHONPATH = "."; python scripts/check_items.py`
- **Verify Schema**: `python scripts/verify_schema.py`
- **Database Dump**: `$env:PYTHONPATH = "."; python scripts/dump_db.py`

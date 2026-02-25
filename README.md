# Scheduler Task Extraction & Vector Search System

This system provides a robust pipeline for scheduling web extraction tasks, storing results in SQL Server 2025, and enabling hybrid (semantic + relational) searching using native SQL Vector support.

## 1. Database Setup

### Prerequisites
- **SQL Server 2025**: Required for native `VECTOR` data type support.
- **Python 3.10+**: Recommended environment.
- **Dependencies**: Install required packages:
  ```bash
  pip install -r requirement.txt
  ```

### Initialization
Initialize the database and schema using `init_db.py`. This script will create the database (if it doesn't exist) and all necessary tables including the `item_embeddings` table with a vector index.

```bash
python init_db.py
```

## 2. Data Import & Pipeline Setup

Follow these steps in order to set up your extraction narrowcast:

### Step 1: Import Items from Excel
Import your target items, sources, and units from an Excel file.
```bash
python data_import/import_items.py path/to/your_file.xlsx
```
*Note: The Excel sheet should contain columns: `Code`, `Description`, `URL`, `Rate`, and `Comments`.*

### Step 2: Register Extractor Scripts
Automatically link your Python extractor scripts (located in `extractors/`) to their corresponding sources in the database.
```bash
python data_import/register_scripts.py
```

### Step 3: Generate Vector Embeddings
Generate semantic embeddings for all imported items to enable vector search.
```bash
python database/backfill_item_embeddings.py
```

## 3. System Architecture

### Core Components
- **Scheduler Core**: Handles job picking, state management, and T-SQL stored procedures.
- **Vector Search**: Uses `all-MiniLM-L6-v2` (384 dimensions) for semantic indexing.
- **Distributed Agents**: 
  - `scheduler_agent.py`: Dispatches due items to Redis.
  - `extractor_agent.py`: Executes Python scripts to crawl data.
  - `database_agent.py`: Saves results back to the database.

### The Search Logic
The system uses a **Hybrid Query** strategy. It combines standard relational filters with semantic similarity.

```sql
SELECT ie.content, VECTOR_DISTANCE('cosine', ie.embedding, @QueryVector) as distance
FROM dbo.item_embeddings ie
JOIN dbo.items i ON ie.item_id = i.id
WHERE i.item_type = 'Electronics' -- Relational Filter
ORDER BY distance ASC;
```

## 4. Maintenance
- **Settings**: Adjust model names, chunk sizes, and connection strings in `settings.yaml`.
- **Search Testing**: Use the `vector_search_test.ipynb` notebook to interactively test and visualize search results.

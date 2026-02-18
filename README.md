# Vector Similarity & Filtering System

This system implements a hybrid search approach in SQL Server 2025, combining **Semantic Vector Search** with **Relational Filters**.

## 1. How Text Embedding Works

The system transforms raw text into mathematical vectors using the following process:

### Model & Architecture
- **Model**: `all-MiniLM-L6-v2` via `sentence-transformers`.
- **Dimensions**: 384 dimensions.
- **Library**: `torch` and `sentence-transformers`.

### Processing Pipeline
1.  **Chunking**: Large text content is split into chunks of 500 characters (configured in `settings.yaml`). This ensures higher search precision.
2.  **Vectorization**: Each chunk is passed through the transformer model to generate a unique 384-float array.
3.  **SQL Storage**: The vector is stored in the `dbo.item_embeddings` table using the native `VECTOR(384)` data type.

## 2. How Filtering Works

The system uses a **Hybrid Query** strategy. It doesn't just search for similarity; it restricts the search space using your existing database relationships.

### The Join Logic
Embeddings are linked to the main `items` and `sources` tables:
- `dbo.item_embeddings.item_id` -> `dbo.items.id`
- `dbo.items.source_id` -> `dbo.sources.source_id`

### SQL Implementation
When you provide a filter (e.g., `{"item_type": "Two Wheeler"}`), the system generates a T-SQL query that:
1.  **Filters First**: Uses standard `WHERE` clauses to identify valid items.
2.  **Search Second**: Calculates `VECTOR_DISTANCE` only within those filtered results.

```sql
SELECT ie.content, VECTOR_DISTANCE('cosine', ie.embedding, @QueryVector) as distance
FROM dbo.item_embeddings ie
JOIN dbo.items i ON ie.item_id = i.id
WHERE i.item_type = 'Two Wheeler' -- This is the filter
ORDER BY distance ASC;
```

## 3. Usage Guide

### Seeding Data
Use `complex_seeder.py` to populate the database with diverse items and pre-calculate their embeddings.

### Testing Search
Run `verify_results.py` to see different filtering scenarios in action:
- **ByCategory**: `vdb.similarity_search("bikes", filters={"item_type": "Two Wheeler"})`
- **BySource**: `vdb.similarity_search("caffeine", filters={"source_id": 5})`

## 4. Troubleshooting
- **Index Errors**: If insertions fail with error `42231` or `8180`, the `VectorDB` class will automatically handle dropping and recreating the vector index to allow the data modification.

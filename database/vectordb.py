import pyodbc
import yaml
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from embeddings.embedder import Embedder

class VectorDB:
    """
    Handles interactions with SQL Server 2025 for vector storage and similarity search.
    """

    def __init__(self, config_path: str = "settings.yaml"):
        """
        Initializes the VectorDB with settings from settings.yaml.

        Args:
            config_path (str): Path to the settings.yaml file.
        """
        self.config = self._load_config(config_path)
        self.conn_str = self.config.get("sql_connection_string")
        self.chunk_size = self.config.get("chunk_size", 500)
        self.embedder = Embedder(config_path)

    def _load_config(self, config_path: str) -> dict:
        """Loads configuration from a YAML file."""
        path = Path(config_path)
        if not path.exists():
            return {}
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def _get_connection(self):
        """Creates a new pyodbc connection."""
        return pyodbc.connect(self.conn_str)

    def _chunk_text(self, text: str, size: int) -> List[str]:
        """Splits text into chunks of specified size."""
        if not text:
            return []
        return [text[i : i + size] for i in range(0, len(text), size)]

    def add_document(self, item_id: int, content: str):
        """
        Splits content into chunks, generates embeddings, and inserts into SQL Server.
        Handles the case where a VECTOR INDEX might block insertions (Error 42231).

        Args:
            item_id (int): Foreign key to dbo.items.
            content (str): The text content to store and index.
        """
        chunks = self._chunk_text(content, self.chunk_size)
        if not chunks:
            return

        # Generate all embeddings in a single batch for better performance
        embeddings = self.embedder.embed_batch(chunks)
        
        with self._get_connection() as conn:
            # Set autocommit for index operations (Error 574)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Helper to perform the actual inserts
            def _do_insert():
                for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    embedding_json = json.dumps(embedding, separators=(',', ':'))
                    query = """
                    INSERT INTO dbo.item_embeddings (item_id, chunk_index, content, embedding)
                    VALUES (?, ?, ?, CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(384)))
                    """
                    cursor.execute(query, (item_id, idx, chunk, embedding_json))

            try:
                _do_insert()
            except Exception as e:
                # Error 42231: Data modification statement failed because table has a vector index
                # Error 8180: Statement(s) could not be prepared (often related)
                error_str = str(e)
                if "42231" in error_str or "8180" in error_str:
                    print(f"[VectorDB] Handling error: {error_str[:100]}...")
                    print("[VectorDB] Vector index might be blocking insertion. Temporarily dropping index...")
                    cursor.execute("IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_item_embeddings_embedding') DROP INDEX ix_item_embeddings_embedding ON dbo.item_embeddings")
                    
                    # Retry insert
                    _do_insert()
                    
                    # Recreate index
                    print("[VectorDB] Recreating vector index...")
                    cursor.execute("""
                        CREATE VECTOR INDEX ix_item_embeddings_embedding 
                        ON dbo.item_embeddings (embedding)
                        WITH (METRIC = 'COSINE', TYPE = 'DISKANN')
                    """)
                else:
                    raise

    def similarity_search(self, query_text: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Performs a vector similarity search in SQL Server.

        Args:
            query_text (str): The text to search for.
            top_k (int): Number of top results to return.
            filters (dict): Optional filters (source_id, item_type).

        Returns:
            List[Dict[str, Any]]: List of matching documents with distance.
        """
        query_vector = self.embedder.embed(query_text)
        query_vector_json = json.dumps(query_vector, separators=(',', ':'))

        filter_clauses = []
        params = [query_vector_json]

        if filters:
            if "source_id" in filters:
                filter_clauses.append("i.source_id = ?")
                params.append(filters["source_id"])
            if "item_type" in filters:
                filter_clauses.append("i.item_type = ?")
                params.append(filters["item_type"])

        filter_sql = " AND ".join(filter_clauses)
        if filter_sql:
            filter_sql = "WHERE " + filter_sql

        # Vector Distance query for SQL Server 2025
        # Use a simple cast to VECTOR(384) as confirmed by run_sql_test.py
        sql_query = f"""
        SELECT 
            ie.id,
            ie.item_id,
            ie.content,
            i.name as item_name,
            s.source_name as source_name,
            VECTOR_DISTANCE('cosine', ie.embedding, CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(384))) AS distance
        FROM dbo.item_embeddings ie
        JOIN dbo.items i ON ie.item_id = i.id
        LEFT JOIN dbo.sources s ON i.source_id = s.source_id
        {filter_sql}
        ORDER BY distance ASC
        OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
        """
        
        # Adjust params list to include query_vector and then top_k at the end
        final_params = params + [top_k]

        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query, final_params)
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
        
        return results

    def get_all_documents(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all documents with optional filters.

        Args:
            filters (dict): Optional filters (source_id, item_type).

        Returns:
            List[Dict[str, Any]]: List of documents.
        """
        filter_clauses = []
        params = []

        if filters:
            if "source_id" in filters:
                filter_clauses.append("i.source_id = ?")
                params.append(filters["source_id"])
            if "item_type" in filters:
                filter_clauses.append("i.item_type = ?")
                params.append(filters["item_type"])

        filter_sql = " AND ".join(filter_clauses)
        if filter_sql:
            filter_sql = "WHERE " + filter_sql

        sql_query = f"""
        SELECT 
            ie.id,
            ie.item_id,
            ie.content,
            i.name as item_name,
            s.source_name as source_name
        FROM dbo.item_embeddings ie
        JOIN dbo.items i ON ie.item_id = i.id
        LEFT JOIN dbo.sources s ON i.source_id = s.source_id
        {filter_sql}
        """

        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query, params)
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
        
        return results

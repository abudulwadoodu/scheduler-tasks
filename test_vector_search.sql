/*
    SQL Server 2025 Vector Search Test Script
    This script demonstrates the usage of the native VECTOR data type,
    inserting vector data, and performing similarity search using 
    the Cosine Distance operator (<=>).
*/

-- 1. Create a new table to store vector data
-- We use VECTOR(3) for 3-dimensional embeddings as requested.
IF OBJECT_ID('VectorTest', 'U') IS NOT NULL
    DROP TABLE VectorTest;

CREATE TABLE VectorTest (
    Id INT PRIMARY KEY,
    Name NVARCHAR(100),
    Embedding VECTOR(3)
);
GO

-- 2. Insert at least 5 sample rows with different vector values
-- Vectors are represented as string literals in JSON-like array format.
INSERT INTO VectorTest (Id, Name, Embedding)
VALUES 
    (1, 'Alpha Item', '[0.1, 0.2, 0.3]'),
    (2, 'Beta Item', '[0.9, 0.8, 0.7]'),
    (3, 'Gamma Item', '[0.4, 0.5, 0.6]'),
    (4, 'Delta Item', '[0.1, 0.9, 0.1]'),
    (5, 'Epsilon Item', '[0.5, 0.5, 0.5]');
GO

-- 3. Declare a query vector variable
-- This represents the "target" we want to find similar items for.
DECLARE @QueryVector VECTOR(3) = '[0.15, 0.25, 0.35]';

-- 4. Perform similarity search using the VECTOR_DISTANCE function
-- 5. Order results by similarity (closest first)
-- 6. Show the computed distance in result
SELECT 
    Id, 
    Name, 
    Embedding,
    -- VECTOR_DISTANCE(metric, vector1, vector2) is used in SQL Server 2025.
    -- 'cosine' calculates one minus the cosine similarity.
    -- Lower distance means higher similarity.
    VECTOR_DISTANCE('cosine', Embedding, @QueryVector) AS CosineDistance
FROM 
    VectorTest
ORDER BY 
    CosineDistance ASC; -- Closest first
GO

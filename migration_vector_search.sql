/*
    Fixed SQL Migration Script: Add Vector Similarity Search Support
    Database: gor_data_extraction
    Target: SQL Server 2025+
*/

USE gor_data_extraction;
GO

-- 1. Display SQL Server Version for debugging
PRINT 'Working with SQL Server Version:';
SELECT @@VERSION;
GO

-- 2. Correct syntax to enable Preview Features
-- This is often required for the VECTOR data type and index in early 2025/CTP releases.
PRINT 'Enabling PREVIEW_FEATURES...';
ALTER DATABASE SCOPED CONFIGURATION SET PREVIEW_FEATURES = ON;
GO

-- 3. Create the item_embeddings table
IF OBJECT_ID('dbo.item_embeddings', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.item_embeddings (
        id INT IDENTITY(1,1) PRIMARY KEY,
        item_id INT NOT NULL,
        chunk_index INT NULL,
        content NVARCHAR(MAX),
        embedding VECTOR(384) NOT NULL, -- for all-MiniLM-L6-v2
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        
        CONSTRAINT FK_item_embeddings_items FOREIGN KEY (item_id) 
            REFERENCES dbo.items(id) ON DELETE CASCADE
    );
    
    PRINT 'Table dbo.item_embeddings created successfully.';
END
ELSE
BEGIN
    PRINT 'Table dbo.item_embeddings already exists.';
END
GO

-- 4. Add Vector Index
-- Use METRIC and TYPE options for SQL Server 2025.
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_item_embeddings_vector' AND object_id = OBJECT_ID('dbo.item_embeddings'))
BEGIN
    PRINT 'Creating Vector Index...';
    -- Correct syntax for SQL Server 2025 (METRIC and TYPE)
    CREATE VECTOR INDEX IX_item_embeddings_vector 
    ON dbo.item_embeddings (embedding)
    WITH (
        METRIC = 'COSINE',
        TYPE = 'DISKANN'
    );
    
    PRINT 'Vector index IX_item_embeddings_vector created successfully.';
END
GO

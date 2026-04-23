import re
import pyodbc
from scheduler_core.db import engine
from scheduler_core.models import Base
from scheduler_core.config import Config


def _extract_odbc_conn_str(db_url: str) -> str | None:
    """Extracts and URL-decodes the ODBC connect string from a SQLAlchemy mssql+pyodbc URL."""
    match = re.search(r"odbc_connect=(.+)$", db_url)
    if not match:
        return None
    from urllib.parse import unquote_plus
    return unquote_plus(match.group(1))


def _to_master_odbc(odbc_str: str) -> str:
    """Replaces the Database= value in an ODBC string with 'master'."""
    return re.sub(r"Database=[^;]+", "Database=master", odbc_str, flags=re.IGNORECASE)


def _get_db_name(db_url: str) -> str | None:
    """Extracts the database name from the ODBC connect string inside the SQLAlchemy URL."""
    odbc_str = _extract_odbc_conn_str(db_url)
    if not odbc_str:
        return None
    match = re.search(r"Database=([^;]+)", odbc_str, re.IGNORECASE)
    return match.group(1) if match else None


def _is_create_db_file_exists_error(err: Exception) -> bool:
    """
    SQL Server error 5170: cannot create file ... because it already exists.
    pyodbc wraps this as ProgrammingError with a 42000 state in many cases.
    """
    msg = " ".join(str(a) for a in getattr(err, "args", []) if a is not None)
    msg_lower = msg.lower()
    return ("cannot create file" in msg_lower) and ("already exists" in msg_lower or "(5170)" in msg_lower)


def ensure_database_exists():
    """
    For SQL Server: connects to 'master' via raw pyodbc (autocommit=True)
    and creates the target database if it does not already exist.
    Skips silently for SQLite and other non-MSSQL engines.
    """
    if "mssql" not in Config.DB_URL:
        return  # SQLite / other — DB file is created automatically
    print("url : ",Config.DB_URL )
    odbc_str = _extract_odbc_conn_str(Config.DB_URL)
    if odbc_str is None:
        print("Could not parse ODBC connection string; skipping DB creation check.")
        return

    db_name = _get_db_name(Config.DB_URL)
    if not db_name:
        print("Could not determine database name; skipping DB creation check.")
        return

    print(f"Checking if database '{db_name}' exists on SQL Server...")

    master_odbc = _to_master_odbc(odbc_str)
    conn = pyodbc.connect(master_odbc, autocommit=True)
    try:
        cursor = conn.cursor()

        # Check if the database already exists
        cursor.execute("SELECT database_id FROM sys.databases WHERE name = ?", db_name)
        if cursor.fetchone():
            print(f"Database '{db_name}' already exists.")
            return

        print(f"Database '{db_name}' not found — creating it...")

        try:
            # Let SQL Server pick the default file paths.
            cursor.execute(f"CREATE DATABASE [{db_name}]")
            print(f"Database '{db_name}' created successfully.")
        except pyodbc.ProgrammingError as e:
            if _is_create_db_file_exists_error(e):
                raise RuntimeError(
                    f"Cannot create database '{db_name}' because its physical database files already exist on the server. "
                    "This usually happens after a manual rename/detach. Fix the server state (or choose a new database name) "
                    "and retry."
                ) from e
            raise
    finally:
        conn.close()


def _run_units_migration_if_needed():
    """
    Idempotent migration to ensure:
    - dbo.units table exists
    - dbo.items.target_unit_id column exists (renamed from dbo.items.unit_id if present)
    - FK from dbo.items.target_unit_id to dbo.units.unit_id exists

    Runs only for MSSQL; safe to call on every startup.
    """
    if "mssql" not in Config.DB_URL:
        return

    odbc_str = _extract_odbc_conn_str(Config.DB_URL)
    if odbc_str is None:
        return

    conn = pyodbc.connect(odbc_str, autocommit=True)
    try:
        cursor = conn.cursor()

        # 1) Ensure dbo.units table
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM sys.tables t
                WHERE t.name = 'units'
                  AND t.schema_id = SCHEMA_ID('dbo')
            )
            BEGIN
                CREATE TABLE dbo.units (
                    unit_id   INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    unit_code NVARCHAR(20)  NOT NULL UNIQUE,
                    unit_name NVARCHAR(100) NOT NULL,
                    unit_type NVARCHAR(50)  NULL
                );
            END
            """
        )

        # 2) Ensure dbo.items.target_unit_id column and retire legacy dbo.items.unit_id
        cursor.execute(
            """
            -- Only run the items migration logic if dbo.items already exists.
            IF OBJECT_ID('dbo.items', 'U') IS NOT NULL
            BEGIN
                -- Case 1: target_unit_id missing, legacy unit_id present → rename column
                IF COL_LENGTH('dbo.items', 'target_unit_id') IS NULL
                   AND COL_LENGTH('dbo.items', 'unit_id') IS NOT NULL
                BEGIN
                    DECLARE @fk_name_rename sysname;
                    -- Drop any FK that uses dbo.items.unit_id -> dbo.units.unit_id
                    SELECT TOP 1 @fk_name_rename = fk.name
                    FROM sys.foreign_keys fk
                    INNER JOIN sys.foreign_key_columns fkc
                        ON fk.object_id = fkc.constraint_object_id
                    WHERE fk.parent_object_id = OBJECT_ID('dbo.items')
                      AND fk.referenced_object_id = OBJECT_ID('dbo.units')
                      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'unit_id'
                      AND COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) = 'unit_id';

                    IF @fk_name_rename IS NOT NULL
                    BEGIN
                        DECLARE @sql_rename NVARCHAR(MAX);
                        SET @sql_rename = N'ALTER TABLE dbo.items DROP CONSTRAINT [' + @fk_name_rename + N']';
                        EXEC(@sql_rename);
                    END

                    -- Rename the column
                    EXEC sp_rename 'dbo.items.unit_id', 'target_unit_id', 'COLUMN';
                END
                -- Case 2: both columns exist → migrate data then drop legacy unit_id
                ELSE IF COL_LENGTH('dbo.items', 'target_unit_id') IS NOT NULL
                     AND COL_LENGTH('dbo.items', 'unit_id') IS NOT NULL
                BEGIN
                    -- Copy any remaining values from unit_id into target_unit_id
                    EXEC(
                        'UPDATE dbo.items
                         SET target_unit_id = unit_id
                         WHERE target_unit_id IS NULL
                           AND unit_id IS NOT NULL;'
                    );

                    DECLARE @fk_name_drop sysname;
                    SELECT TOP 1 @fk_name_drop = fk.name
                    FROM sys.foreign_keys fk
                    INNER JOIN sys.foreign_key_columns fkc
                        ON fk.object_id = fkc.constraint_object_id
                    WHERE fk.parent_object_id = OBJECT_ID('dbo.items')
                      AND fk.referenced_object_id = OBJECT_ID('dbo.units')
                      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'unit_id'
                      AND COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) = 'unit_id';

                    IF @fk_name_drop IS NOT NULL
                    BEGIN
                        DECLARE @sql_drop NVARCHAR(MAX);
                        SET @sql_drop = N'ALTER TABLE dbo.items DROP CONSTRAINT [' + @fk_name_drop + N']';
                        EXEC(@sql_drop);
                    END

                    ALTER TABLE dbo.items DROP COLUMN unit_id;
                END
                -- Case 3: neither column exists → add target_unit_id
                ELSE IF COL_LENGTH('dbo.items', 'target_unit_id') IS NULL
                     AND COL_LENGTH('dbo.items', 'unit_id') IS NULL
                BEGIN
                    ALTER TABLE dbo.items ADD target_unit_id INT NULL;
                END
            END
            """
        )

        # 3) Ensure FK from dbo.items.target_unit_id to dbo.units.unit_id (only if items table exists)
        cursor.execute(
            """
            IF OBJECT_ID('dbo.items', 'U') IS NOT NULL
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM sys.foreign_keys fk
                    INNER JOIN sys.foreign_key_columns fkc
                        ON fk.object_id = fkc.constraint_object_id
                    WHERE fk.parent_object_id = OBJECT_ID('dbo.items')
                      AND fk.referenced_object_id = OBJECT_ID('dbo.units')
                      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'target_unit_id'
                      AND COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) = 'unit_id'
                )
                BEGIN
                    ALTER TABLE dbo.items
                        ADD CONSTRAINT FK_items_units_target_unit_id
                        FOREIGN KEY (target_unit_id) REFERENCES dbo.units(unit_id);
                END
            END
            """
        )
    finally:
        conn.close()


def _run_sources_migration_if_needed():
    """
    Idempotent migration to ensure a UNIQUE constraint on dbo.sources.base_url.

    Runs only for MSSQL; safe to call on every startup.
    """
    if "mssql" not in Config.DB_URL:
        return

    odbc_str = _extract_odbc_conn_str(Config.DB_URL)
    if odbc_str is None:
        return

    conn = pyodbc.connect(odbc_str, autocommit=True)
    try:
        cursor = conn.cursor()

        # Only run this migration if dbo.sources already exists.
        cursor.execute(
            """
            IF OBJECT_ID('dbo.sources', 'U') IS NOT NULL
            BEGIN
                -- Ensure base_url has a fixed NVARCHAR length so it can be indexed/uniqued.
                -- If base_url is currently NVARCHAR(MAX) (or another non-indexable type),
                -- drop any unique constraint/index on it first, then ALTER, then recreate.
                IF COL_LENGTH('dbo.sources', 'base_url') IS NOT NULL
                BEGIN
                    DECLARE @max_len SMALLINT;
                    DECLARE @type_name SYSNAME;

                    SELECT
                        @max_len = c.max_length,   -- bytes; NVARCHAR(512) = 1024, NVARCHAR(MAX) = -1
                        @type_name = t.name
                    FROM sys.columns c
                    INNER JOIN sys.types t
                        ON c.user_type_id = t.user_type_id
                    WHERE c.object_id = OBJECT_ID('dbo.sources')
                      AND c.name = 'base_url';

                    IF NOT (@type_name = 'nvarchar' AND @max_len = 1024)
                    BEGIN
                        -- Drop UNIQUE constraint on base_url (if any)
                        DECLARE @uq_name sysname;
                        SELECT TOP 1 @uq_name = kc.name
                        FROM sys.key_constraints kc
                        INNER JOIN sys.index_columns ic
                            ON kc.parent_object_id = ic.object_id
                           AND kc.unique_index_id = ic.index_id
                        INNER JOIN sys.columns col
                            ON ic.object_id = col.object_id
                           AND ic.column_id = col.column_id
                        WHERE kc.parent_object_id = OBJECT_ID('dbo.sources')
                          AND kc.type = 'UQ'
                          AND col.name = 'base_url';

                        IF @uq_name IS NOT NULL
                        BEGIN
                            DECLARE @sql_drop_uq NVARCHAR(MAX);
                            SET @sql_drop_uq = N'ALTER TABLE dbo.sources DROP CONSTRAINT [' + @uq_name + N']';
                            EXEC(@sql_drop_uq);
                        END

                        -- Drop UNIQUE index on base_url (if any, and not a constraint)
                        DECLARE @ux_name sysname;
                        SELECT TOP 1 @ux_name = i.name
                        FROM sys.indexes i
                        INNER JOIN sys.index_columns ic
                            ON i.object_id = ic.object_id
                           AND i.index_id = ic.index_id
                        INNER JOIN sys.columns col
                            ON ic.object_id = col.object_id
                           AND ic.column_id = col.column_id
                        WHERE i.object_id = OBJECT_ID('dbo.sources')
                          AND i.is_unique = 1
                          AND i.is_primary_key = 0
                          AND i.is_unique_constraint = 0
                          AND col.name = 'base_url';

                        IF @ux_name IS NOT NULL
                        BEGIN
                            DECLARE @sql_drop_ux NVARCHAR(MAX);
                            SET @sql_drop_ux = N'DROP INDEX [' + @ux_name + N'] ON dbo.sources';
                            EXEC(@sql_drop_ux);
                        END

                        ALTER TABLE dbo.sources ALTER COLUMN base_url NVARCHAR(512) NULL;
                    END
                END

                -- Ensure a UNIQUE constraint on dbo.sources.base_url
                IF NOT EXISTS (
                    SELECT 1
                    FROM sys.key_constraints kc
                    INNER JOIN sys.index_columns ic
                        ON kc.parent_object_id = ic.object_id
                       AND kc.unique_index_id = ic.index_id
                    INNER JOIN sys.columns c
                        ON ic.object_id = c.object_id
                       AND ic.column_id = c.column_id
                    WHERE kc.parent_object_id = OBJECT_ID('dbo.sources')
                      AND c.name = 'base_url'
                      AND kc.type = 'UQ'
                )
                BEGIN
                    ALTER TABLE dbo.sources
                        ADD CONSTRAINT UQ_sources_base_url UNIQUE (base_url);
                END
            END
            """
        )
    finally:
        conn.close()


def init_db():
    print("start")
    ensure_database_exists()
    print("Ensured database exists.")
    _run_units_migration_if_needed()
    _run_sources_migration_if_needed()

    print(f"Connecting to database at: {engine.url}")
    try:
        Base.metadata.create_all(engine)
        print("Database schema initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


if __name__ == "__main__":
    init_db()

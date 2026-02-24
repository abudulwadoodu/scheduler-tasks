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


def init_db():
    ensure_database_exists()

    print(f"Connecting to database at: {engine.url}")
    try:
        Base.metadata.create_all(engine)
        print("Database schema initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


if __name__ == "__main__":
    init_db()

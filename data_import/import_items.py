import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from scheduler_core.db import SessionLocal
from scheduler_core.models import Item, Schedule, Unit, Source


logger = logging.getLogger(__name__)


def _get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_dummy_schedule(session) -> int:
    """
    Ensure there is at least one schedule row and return its id.

    If no schedule exists, create a default one.
    """
    existing = session.query(Schedule).first()
    if existing:
        return existing.id

    schedule = Schedule(
        name="Default Schedule",
        frequency_type="hourly",
        interval_value=60,
        active=True,
        max_retries=3,
        timezone="UTC",
        next_run_time=_get_utc_now(),
    )
    session.add(schedule)
    session.flush()  # populate schedule.id without committing
    logger.info("Created dummy schedule with id %s", schedule.id)
    return schedule.id


def _safe_str(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Optional[object]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_unit_name(value: Optional[object]) -> Optional[str]:
    """
    Normalize the Excel Unit cell (which represents Unit.unit_name).
    """
    return _safe_str(value)


def _generate_unit_code(unit_name: str) -> str:
    """
    Generate a compact unit_code (<= 20 chars) from a unit_name.
    Ensures it is alphanumeric/underscore and upper-cased.
    """
    cleaned = []
    for ch in unit_name.strip():
        if ch.isalnum():
            cleaned.append(ch.upper())
        elif ch in {" ", "-", "/", "."}:
            cleaned.append("_")
        # drop any other punctuation/symbols
    code = "".join(cleaned).strip("_")
    while "__" in code:
        code = code.replace("__", "_")
    return (code or "UNIT")[:20]


def _normalize_base_url(raw_url: Optional[str]) -> Optional[tuple[str, str]]:
    """
    Normalize an arbitrary URL string into:
      - base_url: canonical https://domain (no www)
      - source_name: first domain label (e.g. amazon for amazon.com)
    """
    if not raw_url:
        return None

    raw = raw_url.strip()
    if not raw:
        return None

    parsed = urlparse(raw)

    # If the scheme is missing, default to https
    if not parsed.scheme:
        parsed = urlparse(f"https://{raw}")

    if not parsed.netloc:
        return None

    host = parsed.netloc.lower()

    # Strip leading www.
    if host.startswith("www."):
        host = host[4:]

    # Drop port if present
    host_no_port = host.split(":", 1)[0]

    base_url = f"https://{host_no_port}"

    # Take the first label as the source_name (e.g. amazon from amazon.com)
    source_name = host_no_port.split(".")[0] if host_no_port else ""
    if not source_name:
        return None

    return base_url, source_name


def get_or_create_unit(session, unit_name: str) -> Unit:
    """
    Resolve an Excel 'Unit' (unit_name) to a Unit row.

    - Reuse an existing Unit with the same unit_name (case-insensitive).
    - Otherwise create a new Unit and flush to obtain unit_id.
    - Uses a per-process cache to minimize DB round-trips.
    - Uses a SAVEPOINT (nested transaction) so IntegrityErrors don't rollback the whole import.
    """
    unit_name_norm = _normalize_unit_name(unit_name)
    if not unit_name_norm:
        raise ValueError("unit_name is empty")

    cache = getattr(get_or_create_unit, "_cache", None)
    if cache is None:
        cache = {}
        setattr(get_or_create_unit, "_cache", cache)

    key = unit_name_norm.casefold()
    if key in cache:
        return cache[key]

    # Try existing first (SQL Server typically uses case-insensitive collation; we still normalize in Python)
    existing = session.query(Unit).filter(Unit.unit_name == unit_name_norm).one_or_none()
    if existing is not None:
        cache[key] = existing
        return existing

    base_code = _generate_unit_code(unit_name_norm)

    # Insert with a nested transaction (SAVEPOINT) to gracefully handle race conditions
    for attempt in range(1, 50):
        suffix = "" if attempt == 1 else str(attempt)
        candidate = (base_code[: (20 - len(suffix))] + suffix)[:20]

        unit = Unit(unit_code=candidate, unit_name=unit_name_norm, unit_type=None)
        try:
            with session.begin_nested():
                session.add(unit)
                session.flush()  # populate unit.unit_id
        except IntegrityError:
            # Either unit_code collision or a concurrent insert: re-check by unit_name and retry code if needed
            existing = session.query(Unit).filter(Unit.unit_name == unit_name_norm).one_or_none()
            if existing is not None:
                cache[key] = existing
                return existing
            continue

        cache[key] = unit
        return unit

    raise RuntimeError(f"Could not generate unique unit_code for unit_name='{unit_name_norm}'")


def get_or_create_source(session, url: str) -> Optional[Source]:
    """
    Resolve an item's URL to a Source row.

    - Extract and normalize the base_url from the URL.
    - Reuse an existing Source with that base_url if possible.
    - Otherwise create a new Source and flush to obtain source_id.
    - Uses a simple in-memory cache per process to minimize DB round-trips.
    """
    normalized = _normalize_base_url(url)
    if not normalized:
        return None

    base_url, source_name = normalized

    # Per-process, per-run cache of base_url -> Source
    cache = getattr(get_or_create_source, "_cache", None)
    if cache is None:
        cache = {}
        setattr(get_or_create_source, "_cache", cache)

    if base_url in cache:
        return cache[base_url]

    # First try to find an existing Source in the DB
    existing = session.query(Source).filter_by(base_url=base_url).one_or_none()
    if existing is not None:
        cache[base_url] = existing
        return existing

    # Create a new Source row
    source = Source(
        source_name=source_name,
        source_type="1",
        base_url=base_url,
        login_required=False,
        active=True,
    )
    session.add(source)

    try:
        # Flush so that source_id is populated without committing the transaction.
        # Use a SAVEPOINT so a uniqueness race doesn't rollback the whole import.
        with session.begin_nested():
            session.flush()
    except IntegrityError:
        # Another transaction may have created this Source concurrently.
        # Roll back just this INSERT (savepoint) and try to fetch the existing row.
        logger.warning(
            "IntegrityError when creating Source for base_url '%s'; "
            "assuming race condition and re-querying existing Source.",
            base_url,
        )
        existing = session.query(Source).filter_by(base_url=base_url).one_or_none()
        if existing is None:
            # If it still doesn't exist, propagate the error for the caller to handle.
            raise
        cache[base_url] = existing
        return existing

    cache[base_url] = source
    return source


def import_items_from_excel(file_path: str) -> None:
    """
    Import items from an Excel file into the database.

    Excel columns:
        - Code        -> item_code
        - Description -> name
        - URL         -> url
        - Rate        -> rate
        - Comments    -> comments

    Other fields are hard-coded or auto-generated as required.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    try:
        df = pd.read_excel(path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to read Excel file %s: %s", file_path, exc)
        raise

    required_columns = {"Code", "Description", "URL", "Rate", "Comments"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in Excel: {', '.join(sorted(missing))}")

    # Detect an optional "unit" column (case-insensitive, stripping whitespace/newlines), whose value is a unit_name
    unit_column_name: Optional[str] = None
    for col in df.columns:
        col_label = str(col).strip()
        if col_label.casefold() == "unit":
            unit_column_name = col
            break

    total_rows = len(df)
    rows_inserted = 0
    rows_skipped = 0

    session = SessionLocal()
    try:
        schedule_id = create_dummy_schedule(session)

        # Pre-load units to map unit_name -> unit_id
        units_by_name = {
            _safe_str(unit.unit_name).lower(): unit.unit_id
            for unit in session.query(Unit).all()
            if _safe_str(unit.unit_name)
        }

        # If the Excel has a Unit column, ensure Unit rows exist for all distinct names in the sheet
        units_created = 0
        if unit_column_name is not None:
            seen_unit_names = set()
            for raw in df[unit_column_name].tolist():
                name = _normalize_unit_name(raw)
                if not name:
                    continue
                key = name.lower()
                if key in seen_unit_names:
                    continue
                seen_unit_names.add(key)

                if key not in units_by_name:
                    unit = get_or_create_unit(session, name)
                    units_by_name[key] = unit.unit_id
                    units_created += 1

            if units_created:
                logger.info("Created %s new unit(s) from Excel Unit column", units_created)

        # Pre-load existing items to avoid duplicates by (item_code, url)
        existing_pairs = {
            (row.item_code, row.url)
            for row in session.query(Item.item_code, Item.url).all()
            if row.item_code and row.url
        }

        items_to_insert = []
        now_utc = _get_utc_now()

        for _, row in df.iterrows():
            code = _safe_str(row.get("Code"))
            url = _safe_str(row.get("URL"))

            # Skip rows missing critical identifiers
            if not code or not url:
                rows_skipped += 1
                continue

            key = (code, url)
            if key in existing_pairs:
                rows_skipped += 1
                continue

            description = _safe_str(row.get("Description"))
            comments = _safe_str(row.get("Comments"))
            rate = _safe_float(row.get("Rate"))

            # Determine or create the Source based on the item's URL
            source = get_or_create_source(session, url)
            source_id = source.source_id if source is not None else None

            # Resolve optional unit_name from Excel to target_unit_id
            target_unit_id: Optional[int] = None
            if unit_column_name is not None:
                unit_name_value = _normalize_unit_name(row.get(unit_column_name))
                if unit_name_value:
                    lookup_key = unit_name_value.lower()
                    target_unit_id = units_by_name.get(lookup_key)
                    if target_unit_id is None:
                        # As a fallback, create it on the fly (should be rare because we pre-created units above)
                        unit = get_or_create_unit(session, unit_name_value)
                        target_unit_id = unit.unit_id
                        units_by_name[lookup_key] = target_unit_id

            item = Item(
                item_code=code,
                name=description,
                url=url,
                rate=rate,
                comments=comments,
                source_id=source_id,
                target_unit_id=target_unit_id,
                status="Pending",
                active=True,
                last_run_time=None,
                last_price_updated_at=now_utc,
                no_of_revisions=0,
                instant_flag=False,
                item_type="type_1",
                schedule_id=schedule_id,
            )

            items_to_insert.append(item)
            existing_pairs.add(key)
            rows_inserted += 1

        if items_to_insert:
            # Use bulk insert for performance
            session.bulk_save_objects(items_to_insert)

        session.commit()

        print("Import completed.")
        print(f"Total rows processed: {total_rows}")
        print(f"Rows inserted: {rows_inserted}")
        print(f"Rows skipped: {rows_skipped}")

    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Database error during import: %s", exc, exc_info=True)
        print(f"Import failed due to database error: {exc}")
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Unexpected error during import: %s", exc, exc_info=True)
        print(f"Import failed due to unexpected error: {exc}")
        raise
    finally:
        session.close()


def main(argv: Optional[list[str]] = None) -> None:
    """
    CLI entrypoint.

    Usage:
        python import_items.py path/to/file.xlsx
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("Usage: python import_items.py path/to/file.xlsx")
        raise SystemExit(1)

    excel_path = argv[0]
    import_items_from_excel(excel_path)


if __name__ == "__main__":
    # Configure basic logging if the application hasn't configured it yet
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    main()


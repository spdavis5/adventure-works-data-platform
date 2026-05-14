"""
Web Analytics Prefect Flow

Ingests clickstream data from the Adventure Works Web Analytics API into
Snowflake using an incremental watermark pattern.

Pipeline steps:
  1. Fetch watermark (MAX event_timestamp) from Snowflake
  2. Extract events from the API (with exponential-backoff retries)
  3. Clean / validate with pandas
  4. PUT CSV to @WEB_ANALYTICS_STAGE → COPY INTO RAW_EXT.web_analytics_raw
  5. Cleanup staged files only after a successful load
"""

import os
import time
import tempfile
from datetime import datetime, timezone

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from prefect import flow, task, get_run_logger

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()  # picks up .env when running locally

REQUIRED_FIELDS = [
    "customer_id",
    "product_id",
    "session_id",
    "page_url",
    "event_type",
    "timestamp",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_snowflake_connection() -> snowflake.connector.SnowflakeConnection:
    """Return a fresh Snowflake connection using env vars with error handling."""
    try:
        return snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA", "RAW_EXT"),
            role=os.getenv("SNOWFLAKE_ROLE"),
        )
    except snowflake.connector.Error as e:
        # Logging connection failures specifically
        print(f"Failed to connect to Snowflake: {e}")
        raise


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@task(name="ensure_snowflake_objects", retries=2, retry_delay_seconds=10)
def ensure_snowflake_objects() -> None:
    """
    Ensure the target schema, internal stage, and raw table exist in
    Snowflake.  Runs CREATE ... IF NOT EXISTS so it is safe on every run.
    """
    logger = get_run_logger()
    conn = _get_snowflake_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("CREATE SCHEMA IF NOT EXISTS RAW_EXT")
            cur.execute(
                "CREATE STAGE IF NOT EXISTS RAW_EXT.WEB_ANALYTICS_STAGE "
                "COMMENT = 'Stage for web analytics CSV files uploaded by the Prefect flow'"
            )
            cur.execute("""
                CREATE TABLE IF NOT EXISTS RAW_EXT.web_analytics_raw (
                    customer_id       INT            NOT NULL,
                    product_id        INT            NOT NULL,
                    session_id        VARCHAR(255)   NOT NULL,
                    page_url          VARCHAR(1000),
                    event_type        VARCHAR(50),
                    event_timestamp   TIMESTAMP_NTZ  NOT NULL,
                    _loaded_at        TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),
                    _file_name        VARCHAR(255)
                )
            """)
            logger.info("Snowflake objects verified (schema / stage / table).")
        except snowflake.connector.ProgrammingError as e:
            logger.error(f"Snowflake DDL execution failed: {e}")
            raise
        finally:
            cur.close()
    finally:
        conn.close()


@task(name="fetch_watermark", retries=2, retry_delay_seconds=10)
def fetch_watermark() -> str | None:
    """
    Query MAX(event_timestamp) from the target table.

    Returns the ISO-8601 string of the latest timestamp, or None if the
    table is empty (first-run scenario).
    """
    logger = get_run_logger()
    conn = _get_snowflake_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT MAX(event_timestamp) FROM RAW_EXT.web_analytics_raw")
            row = cur.fetchone()
            
            if row is None or row[0] is None:
                logger.info("No existing watermark found — first run detected.")
                return None

            # Snowflake returns a datetime object; convert to ISO string
            watermark = row[0]
            if isinstance(watermark, datetime):
                watermark_str = watermark.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                watermark_str = str(watermark)

            logger.info(f"Watermark fetched: {watermark_str}")
            return watermark_str
        except snowflake.connector.Error as e:
            logger.error(f"Failed to query watermark from Snowflake: {e}")
            raise
        finally:
            cur.close()
    finally:
        conn.close()


@task(name="extract_events", retries=3, retry_delay_seconds=[5, 15, 45])
def extract_events(since: str | None) -> list[dict]:
    """
    GET clickstream events from the API.

    Uses exponential backoff for 5xx and 429 errors.
    Applies a 30-second timeout to each request.
    """
    logger = get_run_logger()
    api_base_url = os.getenv("API_BASE_URL", "http://localhost:5001")
    url = f"{api_base_url}/analytics/clickstream"

    params = {}
    if since is not None:
        params["since"] = since

    max_retries = 5
    backoff = 2  # seconds – initial delay

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=30)

            # Handle rate-limiting (429)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", backoff))
                logger.warning(
                    f"Rate limited (429). Retrying after {retry_after}s "
                    f"(attempt {attempt}/{max_retries})."
                )
                time.sleep(retry_after)
                backoff *= 2
                continue

            # Handle server errors (5xx)
            if response.status_code >= 500:
                logger.warning(
                    f"Server error {response.status_code}. Retrying in {backoff}s "
                    f"(attempt {attempt}/{max_retries})."
                )
                time.sleep(backoff)
                backoff *= 2
                continue

            # Raise for any other non-2xx status
            response.raise_for_status()

            events = response.json()
            logger.info(f"Extracted {len(events)} events from API.")
            return events

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(
                f"Network issue (attempt {attempt}/{max_retries}): {e}. "
                f"Retrying in {backoff}s."
            )
            time.sleep(backoff)
            backoff *= 2

    raise RuntimeError(
        f"Failed to extract events after {max_retries} attempts."
    )


@task(name="clean_and_validate")
def clean_and_validate(raw_events: list[dict]) -> pd.DataFrame:
    """
    Clean and validate the raw event list:
      - Drop rows missing any required field.
      - Rename 'timestamp' → 'event_timestamp'.
      - Cast types: customer_id/product_id → int, event_timestamp → datetime.
      - Remove intra-batch exact-duplicate rows.
    """
    logger = get_run_logger()
    df = pd.DataFrame(raw_events)
    initial_count = len(df)

    # --- Drop rows missing any required field ---
    missing_mask = df[REQUIRED_FIELDS].isnull().any(axis=1)
    dropped_count = int(missing_mask.sum())
    if dropped_count:
        logger.warning(f"Dropping {dropped_count} rows with missing required fields.")
    df = df[~missing_mask].copy()

    # --- Rename timestamp → event_timestamp ---
    df.rename(columns={"timestamp": "event_timestamp"}, inplace=True)

    # --- Cast types ---
    df["customer_id"] = df["customer_id"].astype(int)
    df["product_id"] = df["product_id"].astype(int)
    df["event_timestamp"] = pd.to_datetime(
        df["event_timestamp"], utc=True
    ).dt.tz_localize(None)  # TIMESTAMP_NTZ — strip timezone

    # --- Intra-batch deduplication ---
    before_dedup = len(df)
    df.drop_duplicates(inplace=True)
    dupes_removed = before_dedup - len(df)
    if dupes_removed:
        logger.info(f"Removed {dupes_removed} intra-batch duplicate rows.")

    logger.info(
        f"Cleaning complete: {initial_count} raw → {len(df)} clean "
        f"({dropped_count} dropped, {dupes_removed} duplicates removed)."
    )
    return df


@task(name="stage_and_load", retries=2, retry_delay_seconds=15)
def stage_and_load(df: pd.DataFrame) -> None:
    """
    Write the DataFrame to a local CSV, PUT it to the Snowflake internal
    stage, execute COPY INTO, verify the result, and clean up.

    Cleanup of the staged file and local CSV happens only on success.
    """
    logger = get_run_logger()

    # Columns to write — matches the first 6 columns of the target table.
    csv_columns = [
        "customer_id",
        "product_id",
        "session_id",
        "page_url",
        "event_type",
        "event_timestamp",
    ]

    ts_label = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"web_analytics_{ts_label}.csv"

    # Use a temp directory that persists until we finish cleanup
    tmpdir = tempfile.mkdtemp()
    local_path = os.path.join(tmpdir, filename)

    try:
        # --- 1. Write local CSV (with headers) ---
        df[csv_columns].to_csv(local_path, index=False)
        logger.info(f"Local CSV staged: {filename} contains {len(df)} records.")

        conn = _get_snowflake_connection()
        try:
            cur = conn.cursor()

            # --- 2. PUT to internal stage ---
            try:
                put_sql = (
                    f"PUT file://{local_path} @WEB_ANALYTICS_STAGE/ "
                    f"AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
                )
                cur.execute(put_sql)
                logger.info(f"PUT {filename} to Snowflake stage successful.")
            except snowflake.connector.Error as e:
                logger.error(f"Failed to PUT file to Snowflake: {e}")
                raise

            # --- 3. COPY INTO ---
            copy_sql = f"""
                COPY INTO RAW_EXT.web_analytics_raw
                    (customer_id, product_id, session_id,
                     page_url, event_type, event_timestamp)
                FROM @WEB_ANALYTICS_STAGE/{filename}
                FILE_FORMAT = (
                    TYPE = 'CSV'
                    SKIP_HEADER  = 1
                    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                    NULL_IF = ('', 'NULL')
                )
                ON_ERROR = 'ABORT_STATEMENT';
            """
            try:
                results = cur.execute(copy_sql).fetchall()
                
                # --- 4. Verify load result ---
                total_loaded = 0
                total_errors = 0
                for row in results:
                    total_loaded += int(row[3])
                    total_errors += int(row[5])

                if total_errors > 0:
                    raise RuntimeError(
                        f"COPY INTO aborted: {total_errors} errors encountered. "
                        f"Aborting cleanup for debugging."
                    )

                logger.info(f"Snowflake Load Result: {total_loaded} rows inserted, 0 errors.")

                # --- 5. Cleanup (post-success only) ---
                cur.execute(f"REMOVE @WEB_ANALYTICS_STAGE/{filename}")
                logger.info("Internal stage cleanup complete.")

            except snowflake.connector.Error as e:
                logger.error(f"Snowflake COPY INTO failed: {e}")
                raise
            finally:
                cur.close()
        finally:
            conn.close()

        # Delete local CSV after successful load
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"Local temp file {filename} deleted.")

    except Exception as e:
        logger.error(
            f"Pipeline Stage/Load error: {str(e)}. Files preserved in {tmpdir}"
        )
        raise
    finally:
        # Best-effort removal of the temp directory
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------

@flow(name="web-analytics-flow", log_prints=True)
def web_analytics_flow() -> None:
    """
    Incremental ingestion flow:
      1. Fetch watermark from Snowflake
      2. Extract new events from the API
      3. Clean and validate
      4. Stage (PUT) and load (COPY INTO) to Snowflake
    """
    logger = get_run_logger()

    # Step 0 — Ensure Snowflake objects exist
    ensure_snowflake_objects()

    # Step 1 — Watermark
    watermark = fetch_watermark()

    # Step 2 — Extract
    raw_events = extract_events(since=watermark)

    if not raw_events:
        logger.info("No new behavioral data found in API. Flow idle.")
        return

    # Step 3 — Clean / Validate
    df = clean_and_validate(raw_events)

    if df.empty:
        logger.info("Zero valid records remained after cleaning. Flow idle.")
        return

    # Step 4 — Stage & Load
    stage_and_load(df)

    logger.info(
        f"Flow Success: {len(df)} records added to RAW_EXT.web_analytics_raw."
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    schedule_minutes = int(os.getenv("FLOW_SCHEDULE_MINUTES", "0"))

    if schedule_minutes > 0:
        # Deployed mode with a schedule
        web_analytics_flow.serve(
            name="web-analytics-scheduled",
            interval=schedule_minutes * 60,
        )
    else:
        # One-shot local execution
        web_analytics_flow()

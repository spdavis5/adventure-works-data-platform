# etl/load.py
import os
import time
import tempfile

def upload_dataframe_to_stage(df, label, stage_name, run_time, file_format="csv"):
    from utils.connections import get_snowflake_connection

    filename = f"{label}_{run_time.strftime('%Y%m%d_%H%M%S')}.{file_format}"
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, filename)

        if file_format == "csv":
            df.to_csv(file_path, index=False, na_rep='')
        elif file_format == "json":
            df.to_json(file_path, orient="records", lines=True)
        else:
            raise ValueError("Unsupported file format for Snowflake upload.")

        print(f"Uploading {filename} to Snowflake stage {stage_name}")

        SNOWFLAKE_SCHEMA=os.getenv("SNOWFLAKE_SCHEMA")

        conn = get_snowflake_connection()
        cs = conn.cursor()
        try:
            cs.execute(f"CREATE SCHEMA IF NOT EXISTS {SNOWFLAKE_SCHEMA};")
            cs.execute(f"CREATE STAGE IF NOT EXISTS {stage_name};")
            cs.execute(f"PUT file://{file_path} @{stage_name}/ OVERWRITE = TRUE")
        finally:
            cs.close()
            conn.close()


def copy_stage_to_table(stage_name, table_name, file_format="CSV", connection=None):
    import time
    start_time = time.time()
    
    metrics = {
        "rows_copied": 0,
        "rows_skipped": 0,
        "execution_time_sec": 0,
        "status": "success",
        "error_message": ""
    }

    try:
        cur = connection.cursor()
        
        # Build SQL based on format
        if file_format.upper() == "CSV":
            # standard CSV loading logic
            sql = f"""
                COPY INTO {table_name}
                FROM @{stage_name}/
                FILE_FORMAT = (
                    TYPE = CSV 
                    SKIP_HEADER = 1 
                    FIELD_OPTIONALLY_ENCLOSED_BY = '\"'
                    NULL_IF = ('', 'NULL')
                )
                ON_ERROR = 'CONTINUE';
            """
        else:
            # JSON loading logic (for variant columns)
            sql = f"""
                COPY INTO {table_name}
                FROM @{stage_name}/
                FILE_FORMAT = (TYPE = JSON)
                ON_ERROR = 'CONTINUE';
            """

        results = cur.execute(sql).fetchall()
        
        # Sum up the results from all files in the stage
        for row in results:
            # row[3] is rows_loaded, row[5] is errors_seen
            metrics["rows_copied"] += int(row[3])
            metrics["rows_skipped"] += int(row[5])

        cur.close()

    except Exception as e:
        metrics["status"] = "error"
        metrics["error_message"] = str(e)
    
    metrics["execution_time_sec"] = round(time.time() - start_time, 2)
    return metrics

def clean_stage(stage_name, connection=None):
    import time
    start_time = time.time()
    
    metrics = {
        "files_removed": 0,
        "execution_time_sec": 0,
        "status": "success",
        "error_message": ""
    }

    try:
        cur = connection.cursor()
        # Execute REMOVE to delete files from the internal stage
        sql = f"REMOVE @{stage_name}/;"
        results = cur.execute(sql).fetchall()
        
        # Each row in the result represents one removed file
        metrics["files_removed"] = len(results)
        cur.close()

    except Exception as e:
        metrics["status"] = "error"
        metrics["error_message"] = str(e)
    
    metrics["execution_time_sec"] = round(time.time() - start_time, 2)
    return metrics
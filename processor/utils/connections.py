# =============================================================================
# processor/utils/connections.py - Database Connection Factory (Milestone 1)
#
# Provides three connection helpers used by the ETL processor:
#   - get_postgres_connection(): Connects to the PostgreSQL source database
#     (orders, order_details tables) using psycopg2.
#   - get_snowflake_connection(): Connects to the Snowflake warehouse where
#     raw data is loaded into RAW_EXT schema via COPY INTO.
#   - get_mongo_collection(): Connects to MongoDB and returns the chat logs
#     collection for extraction.
#
# All credentials come from environment variables (set in .env).
# =============================================================================
import os
import pymongo
import psycopg2
from snowflake.connector import connect


def get_postgres_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

def get_snowflake_connection():
    return connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
    )

def get_mongo_collection():
    client = pymongo.MongoClient(
        host=os.getenv("MONGO_HOST"),
        port=int(os.getenv("MONGO_PORT"))
    )
    db = client[os.getenv("MONGO_DB")]
    return db[os.getenv("MONGO_COLLECTION")]

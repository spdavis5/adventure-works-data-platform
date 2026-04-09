# Product Requirements Document: Web Analytics Ingestion Pipeline

## 1. Problem Statement

Adventure Works needs to see what customers do on the website before they buy. Right now browsing data is stuck in a REST API and not integrated into the data warehouse. Analysts cannot link browsing patterns like page views or add to cart events to actual sales. This prevents the team from understanding the customer journey or calculating conversion rates.

---

## 2. Desired Outcome

The goal is a Prefect 2.0 flow that runs on a schedule to pull web analytics data from the API. The flow will clean and validate the data before loading it into Snowflake. It must use incremental loading to only fetch new events since the last run. By the end, the data will be ready in the RAW_EXT.web_analytics_raw table for dbt modeling.

---

## 3. Acceptance Criteria

- [ ] **Incremental Watermarking:** The flow queries `MAX(event_timestamp)` from `RAW_EXT.web_analytics_raw` at the start.
  - **First-Run Logic:** If the result is NULL (empty table), call the API without the `since` parameter (defaulting to the last 60 minutes).
- [ ] **Atomic Success:** The local CSV and Snowflake staged files are ONLY deleted, and the watermark is ONLY considered "advanced," after the `COPY INTO` command completes without errors in the load result.
- [ ] **Scheduled Orchestration:** The flow must support a configurable schedule defined by the `FLOW_SCHEDULE_MINUTES` environment variable.
- [ ] **HTTP Resilience:** Handles 5xx errors, 429 rate limits (utilizing Retry-After), and request timeouts (set to 30 seconds) using exponential backoff.
- [ ] **Data Validation:** Any row missing ANY required field (as defined in the API schema) is logged and dropped before staging.
- [ ] **Deduplication Scope:** - **Intra-batch:** Exact row-level duplicates within the current batch are removed after cleaning.
  - **Cross-run:** Deduplication across runs is handled downstream in dbt. The flow assumes "at-least-once" delivery and that events are append-only.
- [ ] **Type Integrity:** Renames `timestamp` to `event_timestamp` and explicitly casts to TIMESTAMP_NTZ.
- [ ] **Prefect Observability:** Logging must use Prefect’s logging system so summary statistics (records fetched, dropped, and loaded) are visible in the Prefect UI.
- [ ] **Zero-Record Safety:** If the API returns 0 records, the flow exits successfully without attempting to stage or load data.

---

## 4. Technical Constraints

- **Orchestration:** Use Prefect 2.0+ tasks and flows.
- **Environment:** The flow must be **deployable via the Docker Compose services defined in `compose.yml`** and run within the existing Dockerized environment.
- **Configuration:** All credentials (Snowflake) and URLs (API) must be pulled from the `.env` file located in the project root.
- **Libraries:** Use pandas for data cleaning and snowflake-connector-python for the staging and loading operations.
- **Retries:** Implement standard Prefect retry logic with exponential backoff for all transient network failures.

---

## 5. Data Schema

### API Response Schema (Source)

| Field       | Type   | Description                             | Required? |
| ----------- | ------ | --------------------------------------- | --------- |
| customer_id | int    | AW Customer ID (11000 to 30118)         | Yes       |
| product_id  | int    | AW Product ID (707 to 999)              | Yes       |
| session_id  | string | Format: "sess\_" + 12 hex chars         | Yes       |
| page_url    | string | URL of the interaction                  | Yes       |
| event_type  | string | page_view, click, add_to_cart, purchase | Yes       |
| timestamp   | string | ISO 8601 UTC datetime                   | Yes       |

### Target Table Schema (Snowflake: RAW_EXT.web_analytics_raw)

| Column          | Type          | Source                              |
| --------------- | ------------- | ----------------------------------- |
| customer_id     | INT           | API customer_id                     |
| product_id      | INT           | API product_id                      |
| session_id      | VARCHAR       | API session_id                      |
| page_url        | VARCHAR       | API page_url                        |
| event_type      | VARCHAR       | API event_type                      |
| event_timestamp | TIMESTAMP_NTZ | API timestamp (renamed)             |
| \_loaded_at     | TIMESTAMP_NTZ | Snowflake DEFAULT CURRENT_TIMESTAMP |
| \_file_name     | VARCHAR       | Metadata from COPY INTO             |

---

## 6. Logic & Loading Sequence

1. **Fetch Watermark:** Query `MAX(event_timestamp)` from the target table.
2. **Extract:** GET data from the API using the `since` parameter and a 30-second timeout. Exit if 0 records.
3. **Clean/Validate:** - Rename `timestamp` to `event_timestamp`.
   - Drop rows with ANY missing fields.
   - Cast IDs to INT and timestamps to TIMESTAMP_NTZ.
   - Remove exact row-level duplicates within the batch.
4. **Stage:** Write to a local temporary CSV (with headers). PUT to @WEB_ANALYTICS_STAGE.
5. **Load:** Execute `COPY INTO RAW_EXT.web_analytics_raw`. Ensure the command completes without errors.
6. **Cleanup (Post-Success Only):** - REMOVE file from @WEB_ANALYTICS_STAGE.
   - Delete local temporary CSV.

---

## 7. Quality & Testing (dbt Layer)

- **Source Freshness:** Support dbt source freshness checks (12h warn and 24h error).
- **Referential Integrity:** Must pass relationships tests linking `customer_id` back to stg_adventure_db\_\_customers.
- **Categorical Validation:** `event_type` must be validated via accepted_values (page_view, click, add_to_cart, purchase).

---

## 8. Project Integration

- **Implementation Path:** The Python code for this flow should be written to `prefect/flows/web_analytics_flow.py`.
- **API Interaction:** The flow must interact with the API at the URL stored in the API_BASE_URL environment variable.
- **Scheduling:** The flow should be deployed with a schedule that respects the FLOW_SCHEDULE_MINUTES variable.

---

## 9. Questions and Assumptions

- **Assumption:** The pipeline only handles append-only data ordered by `event_timestamp`. Late-arriving data from the source is out of scope.
- **Assumption:** The snowflake-connector-python is the primary library for staging and loading operations.
- **Assumption:** The batch size is small enough to fit in the container memory before writing to disk.

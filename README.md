[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/7Tkgt8hQ)

# Adventure Works Data Platform

> An end-to-end data platform that extracts sales, customer, chat, and web analytics data from four heterogeneous sources, loads it into Snowflake, transforms it with dbt, and exposes the models to AI agents through an MCP server.

## Architecture

```text
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  PostgreSQL  │  │   MongoDB    │  │   REST API   │  │  CSV Files   │
│ (Sales Data) │  │ (Chat Logs)  │  │ (Clickstream)│  │  (Ref Data)  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       └───────┬─────────┘                 │                 │
               v                           v                 v
      ┌─────────────────┐           ┌──────────────┐  ┌──────────────┐
      │   Python ETL    │           │   Prefect    │  │     dbt      │
      │   Processor     │           │     Flow     │  │    Seeds     │
      └────────┬────────┘           └──────┬───────┘  └──────┬───────┘
               │ PUT Files                 │                 │
               v                           │                 │
      ┌─────────────────┐                  │                 │
      │   Snowflake     │                  │                 │
      │Internal @Stages │                  │                 │
      └────────┬────────┘                  │                 │
               │ COPY INTO                 │                 │
               v                           v                 v
┌────────────────────────────────────────────────────────────────────┐
│               Snowflake Warehouse (RAW_EXT Schema)                 │
│  {orders_raw} {chat_logs_raw} {web_analytics_raw}  {ship_method}   │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │
                                   v
┌────────────────────────────────────────────────────────────────────┐
│                       dbt Models (Warehouse)                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      1. Staging Models                       │  │
│  │     (stg_ecom__*, stg_adventure_db__*, stg_real_time__*,     │  │
│  │                     stg_web_analytics)                       │  │
│  └───────────────────────────────┬──────────────────────────────┘  │
│                                  │                                 │
│                                  v                                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    2. Intermediate Models                    │  │
│  │  (int_sales_order_line_items, int_web_analytics_with_cust.,  │  │
│  │   int_sales_orders_with_campaign, int_sales_order_with_...)  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         v                         v                         v
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│    Snowsight     │      │    dbt Cloud     │      │  dbt MCP Server  │
│    Dashboard     │      │     (CI/CD)      │      │   (Port: 8000)   │
└──────────────────┘      └──────────────────┘      └────────┬─────────┘
                                                             │
                                                             v
                                                    ┌──────────────────┐
                                                    │    AI Agents     │
                                                    │  (Consumers)     │
                                                    └──────────────────┘
```

**Caption:** Data flows from four source systems through extraction and staging into Snowflake, where dbt transforms it into clean staging and intermediate models. The final data serves dashboards, CI/CD pipelines, and an MCP server for AI agent interaction.

---

## Problem Statement

Adventure Works has operational data spread across multiple systems. Sales orders and customer records live in PostgreSQL, customer support chat logs are stored in MongoDB, marketing campaign data arrives in CSV files, and web analytics clickstream events come from a REST API. Without a unified platform, stakeholders cannot answer cross-cutting questions like "Which marketing campaigns drove the most revenue?" or "How does web behavior differ between customers who open support tickets and those who do not?" This platform consolidates all four sources into a single Snowflake warehouse and transforms the data into analysis-ready models with full lineage and documentation.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Source Systems | PostgreSQL, MongoDB, REST API | These represent the kind of heterogeneous sources found in real companies. Relational databases, document stores, and APIs each require different extraction strategies, which forces the pipeline to handle diverse data formats. |
| Extraction | Python ETL Processor | A custom processor allows watermark-based incremental loading, which avoids re-extracting unchanged data. The processor stages files locally before loading them into Snowflake via COPY INTO for efficient bulk ingestion. |
| Warehouse | Snowflake | Snowflake separates compute from storage, so the warehouse can scale down when idle without losing data. Its native support for semi-structured data (VARIANT columns) handles the nested JSON from MongoDB chat logs and the order details array without requiring a separate transformation step. |
| Transformation | dbt | dbt provides version-controlled SQL transformations with built-in testing, lineage tracking, and documentation generation. This means the data team can validate data quality on every commit and trace how a column flows from source to analytics. |
| Orchestration | Prefect | Prefect handles the web analytics ingestion flow with built-in retries, logging, and scheduling. It was simpler to configure than Airflow for this project while still providing full observability into task execution and failures. |
| CI/CD | dbt Cloud + GitHub | dbt Cloud runs automated builds on a daily cadence and triggers test suites on every pull request. This prevents breaking changes from reaching the production schema. |
| Agent Access | dbt MCP Server | MCP exposes the dbt project's models, descriptions, compiled SQL, and lineage to AI agents. An agent can discover models, read column documentation, and trace dependencies without needing direct database access. |
| Containerization | Docker Compose | Docker Compose ensures every service (PostgreSQL, MongoDB, Prefect, the processor, and the MCP server) runs in a reproducible environment. A new developer can clone the repo and run `docker compose up` to get the full platform running. |

---

## Data Flow

**Ingestion.** Data enters the platform from four sources. The Python ETL processor extracts sales orders and order details from PostgreSQL, and chat logs from MongoDB. It stages each batch as JSON/CSV files locally, then loads them into Snowflake's RAW_EXT schema via internal stages and COPY INTO. For web analytics, a Prefect flow polls the REST API on a configurable schedule, using watermark-based incremental loading to pull only new clickstream events since the last run. Customer, product, vendor, and campaign data are ingested either via existing batch pipelines or as dbt seeds.

**Transformation.** dbt processes the raw data in two layers. Staging models (like `stg_ecom__sales_orders`, `stg_adventure_db__customers`, and `stg_web_analytics`) clean, cast, and rename columns from their raw source format. Some staging models are more complex, for example `stg_ecom__sales_orders` unions legacy batch data with real-time streaming orders, converts text-based delivery estimates into numeric days, and resolves shipping method IDs to human-readable names. Intermediate models then join across sources. `int_sales_order_line_items` flattens the nested order details array into one row per line item. `int_sales_order_with_customers` enriches orders with customer demographics. `int_sales_orders_with_campaign` attributes orders to marketing campaigns. `int_web_analytics_with_customers` joins clickstream events to customer profiles for behavioral analysis.

**Serving.** The transformed data is consumed through three channels. A Snowsight dashboard visualizes 30-day sales trends and order metrics. dbt Cloud runs daily production builds and CI/CD test suites on pull requests. The dbt MCP server exposes all 20 models with full column-level documentation and lineage to AI agents, enabling programmatic data discovery and SQL compilation.

---

## Setup and Run

### Prerequisites
- Docker Desktop
- Snowflake account (trial works)
- Python 3.9+
- dbt Cloud account (free tier)
- uv (Python package manager)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/byu-is-566/is-566-11-final-project-spdavis5-1.git
cd is-566-11-final-project-spdavis5-1

# 2. Configure environment
cp .env.sample .env
# Edit .env with your Snowflake credentials and API settings

# 3. Start all services (data sources, processor, Prefect, MCP server)
docker compose up -d

# 4. Run dbt models and tests (from the dbt directory)
cd dbt
uv sync
uv run dbt build --profiles-dir . --project-dir .

# 5. Start the MCP server (if not already running via Docker)
docker compose up --build dbt-mcp

# 6. (Optional) Run the MCP demo client
cd ../mcp
uv sync
uv run python demo_client.py
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SNOWFLAKE_ACCOUNT` | Full Snowflake account identifier (e.g., `ab12345.us-east-1`) |
| `SNOWFLAKE_USER` | Snowflake username |
| `SNOWFLAKE_PASSWORD` | Snowflake password |
| `SNOWFLAKE_WAREHOUSE` | Compute warehouse name (e.g., `COMPUTE_WH`) |
| `SNOWFLAKE_DATABASE` | Target database |
| `SNOWFLAKE_ROLE` | Snowflake role (default: `ACCOUNTADMIN`) |
| `API_BASE_URL` | Web Analytics REST API endpoint |
| `PREFECT_API_URL` | Prefect server API endpoint |
| `FLOW_SCHEDULE_MINUTES` | Frequency for the Prefect web analytics flow |

See `.env.sample` for the full list.

---

## Project Milestones

### Milestone 1: Core Pipeline
Built the foundational data pipeline from scratch. Developed a containerized Python ETL microservice to extract recent sales orders and order details from PostgreSQL, and chat logs from MongoDB using watermark dates, staging them locally before loading to Snowflake via COPY INTO. Created 18 dbt models across three layers: 5 base models for raw data parsing, 10 staging models for cleaning and standardization (including using `ARRAY_AGG` to reverse lateral flattening and nest order details), and 3 intermediate models for cross-source joins. Implemented 5 generic tests (unique, not_null, accepted_values, relationships) and 4 singular SQL tests for business logic validation. Loaded 2 seed files (`ship_method`, `measures`) for reference data. Built a Snowsight dashboard analyzing sales over the past 30 days by date and country to prove end-to-end functionality.

### Milestone 2: Orchestration, Quality, and Agent-Assisted Development
Added web analytics ingestion via Prefect, pulling clickstream events from a REST API with watermark-based incremental loading. Created `stg_web_analytics` and `int_web_analytics_with_customers` to join clickstream data with customer profiles. Configured source freshness monitoring with a 12-hour warn and 24-hour error threshold on web analytics data. Integrated dbt Cloud for scheduled production builds and CI/CD on pull requests. Added 2 singular tests for web analytics data quality.

### Milestone 3: Agent Access and Portfolio
Deployed the dbt MCP server in Docker Compose, exposing all 20 models to AI agents via SSE. Upgraded every model and column description in `models.yml` to be agent-friendly, with grain statements, join targets, primary/foreign key annotations, and business context. Built a Python demo client that connects to the MCP server and demonstrates tool discovery, model listing, model details, SQL compilation, and lineage traversal. Wrote a reflection on agent data access patterns and production considerations.

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Processed Volume | 68,365 Orders, 19,119 Customers, 1,185 Analytics Events, 141 Chat Logs |
| Pipeline Execution Time | ~7.2 seconds per microservice cycle |
| dbt model count | 20 |
| dbt test count | 19 (generic + singular) |
| Test pass rate | 100% (blocking CI/CD requirements) |
| Data sources integrated | 5 (PostgreSQL, MongoDB, REST API, CSV seeds) |
| Models exposed via MCP | 20 |

---

## What I Learned

The biggest lesson from this project was that documentation is not an afterthought. When I first tried to write agent-friendly YAML descriptions, I gave an AI assistant my models without enough context and got back inaccurate column names and descriptions. I had to provide the actual SQL for each model and verify every column name by hand. That process taught me that even with AI assistance, the data engineer is responsible for the accuracy of the metadata. I also learned that small configuration details matter more than I expected. A missing `version: 2` header in my YAML file caused dbt to silently ignore all 1,400 lines of documentation, and it took deliberate debugging to find it. If I were starting over, I would write the documentation alongside each model as I built it rather than going back to document everything at the end. The iterative approach is more accurate and less painful.

---

## Future Improvements

- **Mart Layer**: Add a marts directory with business-ready aggregation models like daily revenue summaries, customer lifetime value, and campaign ROI tables. This would reduce the query complexity for dashboard consumers.
- **Incremental Materializations**: Convert the larger staging models (like `stg_ecom__sales_orders`) from full table rebuilds to incremental materializations. This would reduce build times and Snowflake compute costs as data volume grows.
- **Role-Based MCP Access**: Implement access controls on the MCP server so that agents can only see models relevant to their domain. Sensitive columns like credit card approval codes or email addresses should be masked or excluded depending on the agent's role.

---

## Technical Decisions

See [technical_decisions.md](technical_decisions.md) for detailed documentation of key architectural choices.

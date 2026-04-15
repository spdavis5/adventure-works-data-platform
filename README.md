[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/7Tkgt8hQ)

# Adventure Works Data Platform

> An end-to-end data platform that extracts sales, customer, chat, and web analytics data from four sources, loads it into Snowflake, transforms it with dbt, and exposes the models to AI agents through an MCP server.

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

Adventure Works has operational data spread across multiple systems. Sales orders and customer records live in PostgreSQL, customer support chat logs sit in MongoDB, marketing campaign data arrives in CSV files, and web analytics clickstream events come from a REST API. Without a single place to query all of this, there is no easy way to answer cross-cutting questions like "Which marketing campaigns drove the most revenue?" or "How does web behavior differ between customers who open support tickets and those who do not?"

I built this platform to consolidate all four sources into a single Snowflake warehouse and transform the raw data into clean, analysis-ready models with full lineage and documentation. The final milestone adds an AI agent access layer so that an LLM can discover and query the models programmatically.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Source Systems | PostgreSQL, MongoDB, REST API | These represent the kind of sources you find at real companies. Relational databases, document stores, and APIs each need different extraction strategies, which forces the pipeline to handle diverse data formats. |
| Extraction | Python ETL Processor | I built a custom processor so I could use watermark-based incremental loading, which avoids re-extracting data that has not changed. The processor stages files locally before loading them into Snowflake via COPY INTO for efficient bulk ingestion. |
| Warehouse | Snowflake | Snowflake separates compute from storage, so the warehouse can scale down when idle without losing data. Its native support for semi-structured data (VARIANT columns) handles the nested JSON from MongoDB chat logs and the order details array without needing a separate transformation step. |
| Transformation | dbt | dbt gives me version-controlled SQL transformations with built-in testing, lineage tracking, and documentation generation. That means data quality gets validated on every commit and I can trace how any column flows from source to analytics. |
| Orchestration | Prefect | Prefect handles the web analytics ingestion flow with built-in retries, logging, and scheduling. It was simpler to configure than Airflow for this project while still giving me full observability into task execution and failures. |
| CI/CD | dbt Cloud + GitHub | dbt Cloud runs automated builds on a daily schedule and triggers test suites on every pull request. This prevents breaking changes from reaching the production schema. |
| Agent Access | dbt MCP Server | MCP exposes the dbt project's models, descriptions, compiled SQL, and lineage to AI agents. An agent can discover models, read column documentation, and trace dependencies without needing direct database access. |
| Containerization | Docker Compose | Docker Compose ensures every service (PostgreSQL, MongoDB, Prefect, the processor, and the MCP server) runs in a reproducible environment. Someone can clone the repo and run `docker compose up` to get the full platform running. |

---

## Data Flow

Data enters the platform from four sources. The Python ETL processor extracts sales orders and order details from PostgreSQL, and chat logs from MongoDB. It stages each batch as JSON/CSV files locally, then loads them into Snowflake's RAW_EXT schema via internal stages and COPY INTO. For web analytics, a Prefect flow polls the REST API on a configurable schedule, using watermark-based incremental loading to pull only new clickstream events since the last run. Customer, product, vendor, and campaign data come in through existing batch pipelines or as dbt seeds.

From there, dbt processes the raw data in two layers. Staging models like `stg_ecom__sales_orders`, `stg_adventure_db__customers`, and `stg_web_analytics` clean, cast, and rename columns from their raw source format. Some are more involved than others. For example, `stg_ecom__sales_orders` unions legacy batch data with real-time streaming orders, converts text-based delivery estimates into numeric days, and resolves shipping method IDs to human-readable names. Intermediate models then join across sources. `int_sales_order_line_items` flattens the nested order details array into one row per line item, `int_sales_order_with_customers` enriches orders with customer demographics, `int_sales_orders_with_campaign` attributes orders to marketing campaigns, and `int_web_analytics_with_customers` joins clickstream events to customer profiles for behavioral analysis.

The transformed data is consumed through three channels: a Snowsight dashboard for 30-day sales trends, dbt Cloud for daily production builds and CI/CD, and the dbt MCP server which exposes all 20 models with full column-level documentation and lineage to AI agents.

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
I built the foundational data pipeline from scratch. I developed a containerized Python ETL microservice to extract recent sales orders and order details from PostgreSQL, and chat logs from MongoDB using watermark dates, staging them locally before loading to Snowflake via COPY INTO. I created 18 dbt models across three layers: 5 base models for raw data parsing, 10 staging models for cleaning and standardization (including using `ARRAY_AGG` to reverse lateral flattening and nest order details), and 3 intermediate models for cross-source joins. I implemented 5 generic tests (unique, not_null, accepted_values, relationships) and 4 singular SQL tests for business logic validation. I loaded 2 seed files (`ship_method`, `measures`) for reference data and built a Snowsight dashboard analyzing sales over the past 30 days by date and country to prove end-to-end functionality.

### Milestone 2: Orchestration, Quality, and Agent-Assisted Development
I added web analytics ingestion via Prefect, pulling clickstream events from a REST API with watermark-based incremental loading. I created `stg_web_analytics` and `int_web_analytics_with_customers` to join clickstream data with customer profiles. I configured source freshness monitoring with a 12-hour warn and 24-hour error threshold on web analytics data, integrated dbt Cloud for scheduled production builds and CI/CD on pull requests, and added 2 singular tests for web analytics data quality.

### Milestone 3: Agent Access and Portfolio
I deployed the dbt MCP server in Docker Compose, exposing all 20 models to AI agents via SSE. I upgraded every model and column description in `models.yml` to be agent-friendly, with grain statements, join targets, primary/foreign key annotations, and business context. I built a Python demo client that connects to the MCP server and demonstrates tool discovery, model listing, model details, SQL compilation, and lineage traversal. I also wrote a reflection on agent data access patterns and production considerations.

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

This project fundamentally changed how I approach large-scale data engineering in an AI-augmented workflow. I realized that the primary friction point often isn't the AI's lack of technical reasoning, but rather the human failure to provide quality context and specificity. Clearly communicating expectations and requirements and anticipating potential issues is becoming an increasingly important skill for architecting robust systems and pipelines with AI. A few prompts I fed to AI agents during this project weren't specific enough, or didn't provide enough context, which caused me to have to edit code manually and troubleshoot to get the desired result. This took extra time and effort that could have been avoided with more upfront planning and anticipation.

---

## Future Improvements

- **Pipeline Alerting**: Enhance the Prefect orchestration to trigger automated Slack or email alerts if the web analytics extraction or any upstream database pulls fail, ensuring immediate visibility into pipeline outages.
- **Incremental Materializations**: Convert the larger staging models (like `stg_ecom__sales_orders`) from full table rebuilds to incremental materializations. This would reduce dbt build times and Snowflake compute costs as data volume grows.
- **Role-Based MCP Access**: Implement access controls on the MCP server so that departmental agents can only see models relevant to their domain. By doing this, sensitive columns like customer email addresses could be dynamically masked or excluded depending on the agent's role.

[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/7Tkgt8hQ)

# Final Project

The always-up-to-date instructions for this assignment can be found [here](https://github.com/byu-is-566/is-566-11-final-project-instuctions).

I'd recommend that you only access the instructions via the web so that you always have the latest copy.

Oh and **refresh often** so you don't miss updates.

---

## Milestone 2: Web Analytics & DataOps Integration

### 1. What I Built and Why

In this milestone, I expanded the platform to ingest near real-time behavioral data. The objective was to create a unified view of the customer by combining legacy sales records with modern web clickstream events.

The most satisfying part of this build was successfully creating the intermediate view, where I could see customer profile data joined directly with the new web analytics data extracted from the REST API.

---

### 2. Architecture Diagram

This diagram illustrates the flow from multiple data sources through ingestion, transformation, and analytics layers into the final warehouse outputs.

```text
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  PostgreSQL  │  │   MongoDB    │  │   REST API   │  │  CSV Files   │
│ (Sales/M1)   │  │  (Chat/M1)   │  │(Analytics/M2)│  │ (Campaigns)  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       v                 v                 v                 v
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│    Python    │  │    Python    │  │   Prefect    │  │     dbt      │
│   Processor  │  │   Processor  │  │     Flow     │  │    Seeds     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       v                 v                 v                 v
┌──────────────────────────────────────────────────────────────────┐
│                     Snowflake Warehouse (Raw)                    │
│ {orders_raw}   {chat_logs_raw}  {web_analytics_raw}  {campaigns} │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 v
┌──────────────────────────────────────────────────────────────────┐
│                       dbt Models (Warehouse)                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    1. Staging Models                       │  │
│  │     (stg_orders, stg_customers, stg_web_analytics)         │  │
│  └─────────────────────────────┬──────────────────────────────┘  │
│                                │                                 │
│                                v                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  2. Intermediate Models                    │  │
│  │(int_sales_with_customers, int_web_analytics_with_customers)│  │
│  └────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
        ┌────────────────────────┴────────────────────────┐
        │                                                 │
        v                                                 v
┌──────────────────────────────┐        ┌──────────────────────────────┐
│     Snowsight Dashboard      │        │      Enriched Analytical     │
│    (30-Day Sales Trends)     │        │      Web clickstream Data    │
└──────────────────────────────┘        └──────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                           dbt Cloud                              │
│         (Scheduled Production Build & CI/CD PR Testing)          │
└──────────────────────────────────────────────────────────────────┘
```

---

### 3. Data Quality Strategy

To maintain a reliable "Gold" layer in the warehouse, I implemented a multi-tiered validation strategy:

- **Generic Tests:** Built-in dbt tests for `unique`, `not_null`, `accepted_values`, and `relationships` ensure structural integrity across staging and mart models.
- **Custom Singular Tests:** SQL-based tests verify business logic, such as ensuring each order has exactly one conversion event and that product inventory remains positive.
- **Source Freshness:** Configured dbt to monitor the `event_timestamp` in our web analytics source, alerting the team if data ingestion lags by more than 12 hours.

---

### 4. dbt Cloud Orchestration

The transition to dbt Cloud felt natural since it utilizes the same repository while adding more advanced controls. The GUI provides a convenient way to monitor complex runs and manage the automated lifecycle of the data.

- **Scheduled Builds:** Runs `dbt build` on a daily or hourly cadence to refresh the `dbt_prod` schema.
- **CI/CD:** Automatically triggers a build and test sequence on every GitHub Pull Request to prevent breaking changes from reaching production.

---

### 5. Setup & Environment

Detailed reflections on the development of the Prefect ingestion pipeline can be found in the Agent Log (`prefect/agent_log.md`).

To run this project locally, the following new environment variables are required in your `.env` file:

- `API_BASE_URL`: The endpoint for the Web Analytics REST API.
- `PREFECT_API_URL`: The local or cloud endpoint for the Prefect orchestration server.
- `FLOW_SCHEDULE_MINUTES`: Frequency at which the Prefect flow polls for new API data.

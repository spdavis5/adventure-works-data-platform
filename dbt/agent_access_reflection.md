# Agent Data Access Reflection

> Now that you've set up the dbt MCP server and seen an AI agent interact with your data models, take some time to think critically about what this means for data engineering. This reflection should be thoughtful (500-800 words), not a checklist.

---

## 1. What Worked Well

The MCP server's lineage traversal was a feature that worked well. When I queried the lineage for `stg_ecom__sales_orders`, the agent traced the full dependency tree. It found the upstream path through `base_ecom__sales_orders` and `stg_real_time__sales_orders` back to the raw sources, and it mapped the downstream path through all three intermediate models. The tool discovery step also worked well and listed every available tool, understood the parameter schemas, and called the right endpoints.

---

## 2. What Was Difficult or Confusing

The hardest part was realizing that I could not just hand my YAML file to an AI assistant and expect perfect documentation back. My first attempt was too broad. I gave the AI my `models.yml` and the documentation guide without enough context about the actual SQL transformations, and the results had inaccuracies. For example, the AI documented `stg_ecom__sales_orders` with column names like `subtotal`, `ship_method`, and `delivery_estimate` instead of the actual output names `sub_total`, `shipping_method`, and `delivery_estimate_days`. It also listed columns like `order_detail` (singular) when the SQL actually produces `order_details` (plural). These are small differences, but an agent trying to query `subtotal` when the column is actually `sub_total` would fail. I had to go back, provide the AI with the actual SQL files for each model, and ask it to cross-reference every column name against the real output. AI-assisted documentation requires careful verification and you cannot skip the step of reading the SQL yourself.

---

## 3. Documentation Quality

The upgrade from minimal descriptions to agent-friendly documentation was an iterative process in this project. My original descriptions were generic one-liners like "Staging model for sales orders." The improved version of `stg_ecom__sales_orders` explains that the model unions legacy batch orders with real-time streaming orders, converts `delivery_estimate` text into `delivery_estimate_days` (for example, "2 days" becomes 2 and "1 week" becomes 7), and resolves the shipping method from the `ship_method` seed table. At the column level, I went from labeling `customer_id` as "Customer ID" to explicitly stating it is a foreign key to `stg_adventure_db__customers.customer_id` and that joining on it brings in customer name, geography, and contact details. The most important lesson was accuracy over volume. I had to remove `product_id` from `stg_ecom__email_campaigns` because the SQL's final CTE drops it even though it exists in the intermediate CTEs. An agent that sees a documented column will try to query it, so a wrong column listing is worse than a missing one.

---

## 4. Production Considerations

Deploying this in a real company would require several safeguards. First, access control. The MCP server currently exposes every model, but a production deployment should restrict visibility based on the agent's role. Sensitive columns like `credit_card_approval_code` or `email_address` would need masking or exclusion. Second, cost management. The `show` tool triggers Snowflake compute, and an agent making frequent queries could run up warehouse costs fast. Rate limiting would be essential. Third, audit logging. Every tool call should be logged with the session ID and query text so data teams can review what the agent accessed. Finally, data freshness metadata should be surfaced so the agent knows whether it is querying data from five minutes ago or five days ago.

---

## 5. Business Use Cases

A marketing analyst could ask "Which email campaigns drove the most revenue last quarter?" The agent would use `int_sales_orders_with_campaign`, which joins orders to campaign attribution via `campaign_id`, `customer_segment`, and `ad_strategy`, to calculate revenue by campaign without the analyst needing to know the schema. A supply chain manager could ask about vendor fulfillment by having the agent join `stg_ecom__purchase_orders` with `stg_adventure_db__vendors` to compare `received_qty` against `order_qty` and flag vendors with high `rejected_qty`. A customer support lead could query `stg_real_time__chat_logs` to segment `rating` by geography or time period. That kind of ad-hoc analysis would normally require a new dashboard request.

---

## 6. The Bigger Picture

Agent access fundamentally expands the data engineer's audience. Traditionally, the downstream consumers were dashboards and reports, which are static artifacts where the data engineer controls the SQL, the joins, and the presentation. With MCP, the consumer is an autonomous agent that writes its own SQL based on the metadata you provide. This means documentation shifts from "nice to have" to load-bearing infrastructure. If a column description is wrong or missing, the agent will produce wrong answers confidently. Data engineers now need to think about grain, join keys, and business context as first-class outputs of their work, not afterthoughts. Schema changes also carry more risk because renaming a column breaks not just dashboards but every agent that learned the old schema. This is an expansion of the role. The pipeline work remains, but the surface area of responsibility grows to include making data genuinely self-describing.

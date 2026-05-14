#!/usr/bin/env python3
"""
dbt MCP Server Demo Client

This script connects to the dbt MCP server running locally via uvx
and demonstrates how an AI agent can discover and interact with your
data models programmatically.

Usage:
    uv run python demo_client.py

Requirements:
    uv sync  (from pyproject.toml)

The MCP server must be running locally:
    cd dbt && MCP_TRANSPORT=sse DBT_PROJECT_DIR=. DBT_PROFILES_DIR=. uvx dbt-mcp
"""

import asyncio
import json
import sys
from datetime import datetime


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
MCP_SERVER_URL = "http://localhost:8000/sse"  # Default dbt-mcp SSE endpoint
OUTPUT_LOG = "demo_output.log"


# -------------------------------------------------------------------
# Helper: log to both console and file
# -------------------------------------------------------------------
log_lines = []


def log(message: str):
    """Print to console and capture for log file."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    log_lines.append(line)


def save_log():
    """Write all captured output to the log file."""
    with open(OUTPUT_LOG, "w") as f:
        f.write(f"dbt MCP Demo Output - {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        for line in log_lines:
            f.write(line + "\n")
    log(f"Output saved to {OUTPUT_LOG}")


# -------------------------------------------------------------------
# Demo Steps
# -------------------------------------------------------------------
def render_tool_result(result) -> str:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return json.dumps(structured, indent=2, default=str)

    content = getattr(result, "content", None)
    if content is None:
        return str(result)

    if isinstance(content, list):
        parts = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(str(text))
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)

    return str(content)


async def run_demo():
    """
    Connect to the dbt MCP server and run a series of demonstrations.
    """

    # Step 0: Import MCP client library
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession

    log("=" * 60)
    log("dbt MCP Server Demo")
    log("=" * 60)
    log("")

    # ----- STEP 1: Connect to the MCP server -----
    log("Step 1: Connecting to dbt MCP server...")

    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            log("Connected successfully!")

            # ----- STEP 2: List available tools -----
            log("")
            log("Step 2: Listing available tools...")
            try:
                tools = await session.list_tools()
                for tool in tools.tools:
                    description = getattr(tool, "description", "") or ""
                    log(f"  - {tool.name}: {description}")
            except Exception as e:
                log(f"Step 2 failed: {e}")

            # ----- STEP 3: List all dbt models -----
            log("")
            log("Step 3: Discovering dbt models...")
            try:
                result = await session.call_tool(
                    "list",
                    {"resource_type": ["model"]},
                )
                log(render_tool_result(result))
            except Exception as e:
                log(f"Step 3 failed: {e}")

            # ----- STEP 4: Get details on a specific model -----
            log("")
            log("Step 4: Getting details for a specific model...")
            try:
                result = await session.call_tool(
                    "get_node_details_dev",
                    {"node_id": "stg_ecom__sales_orders"},
                )
                log(render_tool_result(result))
            except Exception as e:
                log(f"Step 4 failed: {e}")

            # ----- STEP 5: Compile SQL for a model -----
            log("")
            log("Step 5: Compiling SQL for a model...")
            try:
                result = await session.call_tool(
                    "compile",
                    {"models": "int_sales_order_line_items"},
                )
                log(render_tool_result(result))
            except Exception as e:
                log(f"Step 5 failed: {e}")

            # ----- STEP 6: Explore model lineage -----
            log("")
            log("Step 6: Exploring model lineage...")
            try:
                result = await session.call_tool(
                    "get_lineage_dev",
                    {
                        "unique_id": "model.adventure.stg_ecom__sales_orders",
                        "depth": 2,
                    },
                )
                log(render_tool_result(result))
            except Exception as e:
                log(f"Step 6 failed: {e}")

    # ----- WRAP UP -----
    log("")
    log("=" * 60)
    log("Demo complete!")
    log("=" * 60)


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        log("\nDemo interrupted by user.")
    except Exception as e:
        log(f"\nError: {e}")
        log("Make sure the dbt MCP server is running locally.")
        log("Start it with: cd dbt && MCP_TRANSPORT=sse DBT_PROJECT_DIR=. DBT_PROFILES_DIR=. uvx dbt-mcp")
        sys.exit(1)
    finally:
        save_log()
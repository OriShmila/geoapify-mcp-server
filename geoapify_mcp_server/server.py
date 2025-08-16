# Geoapify MCP Server
# Provides access to Geoapify's geocoding, routing, places and location APIs

import json
import logging
import os
from typing import Any

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from geoapify_mcp_server.handlers import (
    TOOL_FUNCTIONS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("GeoapifyMCP")

# Suppress httpx INFO logs to avoid exposing API keys in logs
logging.getLogger("httpx").setLevel(logging.WARNING)


def _package_path(filename: str) -> str:
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, filename)


def load_tool_schemas() -> dict[str, Any]:
    """Load tool schemas bundled in the package."""
    # Prefer package copy; fall back to CWD for local dev
    candidates = [
        _package_path("tools.json"),
        os.path.join(os.getcwd(), "tools.json"),
    ]
    for path in candidates:
        try:
            with open(path, "r") as f:
                schema_data = json.load(f)
            return {tool["name"]: tool for tool in schema_data["tools"]}
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing tools.json at {path}: {e}")
            return {}
    logger.error("tools.json file not found in package or working directory")
    return {}


TOOL_SCHEMAS = load_tool_schemas()
server = Server("GeoapifyAPI")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools: list[types.Tool] = []
    for tool_name, tool_schema in TOOL_SCHEMAS.items():
        tools.append(
            types.Tool(
                name=tool_name,
                description=tool_schema["description"],
                inputSchema=tool_schema["inputSchema"],
                outputSchema=tool_schema["outputSchema"],
            )
        )
    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> Any:
    if name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {name}")

    if arguments is None:
        arguments = {}

    try:
        tool_function = TOOL_FUNCTIONS[name]
        result = await tool_function(**arguments)
        return result
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        raise ValueError(f"Tool execution error: {str(e)}")


async def run_server() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="GeoapifyAPI",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

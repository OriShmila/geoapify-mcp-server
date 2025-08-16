# Geoapify MCP Server entry point

import asyncio
from .server import run_server


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()

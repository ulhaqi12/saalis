# Installation

## Requirements

- Python **3.11** or higher
- An async runtime (the library is fully `asyncio`-native)

## Core library

=== "pip"
    ```bash
    pip install saalis
    ```

=== "uv"
    ```bash
    uv add saalis
    ```

=== "uv (workspace)"
    ```bash
    uv sync --all-packages
    ```

## Optional: HTTP Sidecar

The sidecar is a separate package. Install it if you want to run Saalis as a standalone REST service.

```bash
pip install saalis-sidecar
# or
uv add saalis-sidecar
```

See [HTTP Sidecar](sidecar.md) for usage.

## Optional: MCP Server

The MCP server package exposes Saalis as native MCP tools for Claude Desktop and any MCP-native orchestrator.

```bash
pip install saalis-mcp
# or
uv add saalis-mcp
```

See [MCP Server](mcp.md) for usage.

## Development setup

Clone the repo and install all workspace packages with dev dependencies:

```bash
git clone https://github.com/ulhaqi12/saalis
cd saalis
uv sync --all-packages --extra dev
```

Run the full test suite:

```bash
make all
```

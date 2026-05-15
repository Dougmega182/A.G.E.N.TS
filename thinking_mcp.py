from mcp.server.fastmcp import FastMCP
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from thinking import get_opus_thinking  # import your existing function

mcp = FastMCP("ThinkServer")

@mcp.tool()
def think(task: str) -> str:
    """
    Send a task to the Galaxy AI reasoning engine and get back
    extended step-by-step thinking for the ProseLab 4 project.
    """
    return get_opus_thinking(task)

if __name__ == "__main__":
    mcp.run()
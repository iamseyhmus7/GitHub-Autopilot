import os
from contextlib import AsyncExitStack
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from langchain_mcp_adapters.tools import load_mcp_tools

class MCPConnectionManager:
    _instance = None

    def __init__(self):
        self.stack = AsyncExitStack()
        self.session = None
        self.tools = []

    @classmethod
    async def get_tools(cls):
        if cls._instance is None:
            cls._instance = MCPConnectionManager()
            await cls._instance.connect()
        return cls._instance.tools

    async def connect(self):
        print("[System] Initializing Global MCP Connection to mcp-github-advanced...")
        
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "mcp_github_advanced"],
            env=dict(os.environ)
        )
        
        try:
            transport = await self.stack.enter_async_context(stdio_client(server_params))
            read_stream, write_stream = transport
            
            self.session = await self.stack.enter_async_context(ClientSession(read_stream, write_stream))
            await self.session.initialize()
            
            # Load tools
            self.tools = await load_mcp_tools(self.session)
            print(f"[System] MCP Server Connected. Loaded {len(self.tools)} tools.")
        except Exception as e:
            print(f"[Error] Failed to connect to MCP Server: {e}")
            await self.close()
            raise e

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.stack.aclose()
            cls._instance = None
            print("[System] MCP Connection closed.")

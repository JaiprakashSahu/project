"""
MCP Server for Project LUMEN
============================
The "traffic police" that routes LLM requests to appropriate tools.

This server:
- Maintains a registry of available tools
- Validates incoming tool requests
- Executes tools and returns sanitized results
- Integrates with LLM via the centralized router

SECURITY: The LLM can ONLY interact through this server.
It cannot access the database, Gmail tokens, or execute SQL directly.
"""

import json
from modules.mcp.tools import MCP_TOOLS
from modules.llm.router import llm_router


class MCPServer:
    """
    MCP Server - The control layer between LLM and backend.
    
    Responsibilities:
    1. Tool Discovery: Tell LLM what tools are available
    2. Tool Execution: Run tools when LLM requests them
    3. Error Sanitization: Return safe error messages
    4. LLM Integration: Handle natural language conversations
    
    NOW USES: Centralized LLM Router for all LLM operations.
    Switch between local/groq via LLM_PROVIDER env variable.
    """
    
    def __init__(self):
        """Initialize MCP server with tool registry."""
        self.tools = MCP_TOOLS
        self.llm = llm_router  # Use centralized router
        print("🔧 MCP Server initialized with tools:", list(self.tools.keys()))
    
    # =========================================================================
    # TOOL DISCOVERY
    # =========================================================================
    def get_available_tools(self) -> list:
        """
        Return list of available tools with their schemas.
        This is what the LLM sees to decide which tool to call.
        
        Returns:
            List of tool schemas (OpenAI function calling format)
        """
        tools = []
        for name, config in self.tools.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": config["description"],
                    "parameters": config["parameters"]
                }
            })
        return tools
    
    def get_tool_names(self) -> list:
        """Return just the tool names."""
        return list(self.tools.keys())
    
    # =========================================================================
    # TOOL EXECUTION
    # =========================================================================
    def execute_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """
        Execute a tool by name with given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool
        
        Returns:
            {
                "success": True/False,
                "tool": "tool_name",
                "result": {...} or None,
                "error": "message" or None
            }
        """
        print(f"🔧 MCP executing tool: {tool_name}")
        print(f"   Arguments: {arguments}")
        
        # Validate tool exists
        if tool_name not in self.tools:
            return {
                "success": False,
                "tool": tool_name,
                "result": None,
                "error": f"Unknown tool: {tool_name}. Available: {self.get_tool_names()}"
            }
        
        try:
            # Get the function
            func = self.tools[tool_name]["function"]
            
            # Execute with arguments (or empty dict if none)
            args = arguments or {}
            result = func(**args)
            
            print(f"✅ Tool executed successfully")
            
            return {
                "success": True,
                "tool": tool_name,
                "result": result,
                "error": None
            }
            
        except TypeError as e:
            # Invalid arguments
            error_msg = f"Invalid arguments for {tool_name}: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "tool": tool_name,
                "result": None,
                "error": error_msg
            }
            
        except Exception as e:
            # Generic error - sanitize to not leak internals
            error_msg = f"Tool execution failed: {type(e).__name__}"
            print(f"❌ {error_msg}: {str(e)}")
            return {
                "success": False,
                "tool": tool_name,
                "result": None,
                "error": error_msg
            }
    
    # =========================================================================
    # LLM INTEGRATION (via centralized router)
    # =========================================================================
    def chat(self, user_message: str) -> dict:
        """
        Handle a natural language message from the user.
        
        Flow:
        1. Send message to LLM (via router) with available tools
        2. If LLM wants to call a tool, execute it
        3. Send tool result back to LLM
        4. Return LLM's final explanation
        
        Args:
            user_message: Natural language question from user
        
        Returns:
            {
                "success": True/False,
                "response": "LLM's explanation",
                "tools_used": ["tool1", "tool2"],
                "provider_used": "local" or "groq",
                "error": "message" or None
            }
        """
        print(f"\n{'='*60}")
        print(f"💬 MCP Chat: {user_message[:50]}...")
        print(f"{'='*60}")
        
        tools_used = []
        provider_used = None
        
        try:
            # Step 1: Initial LLM call with tools
            messages = [
                {
                    "role": "system",
                    "content": """You are a helpful financial assistant for Project LUMEN.
You help users understand their spending patterns and financial data.

IMPORTANT RULES:
- You can ONLY access data through the provided tools
- You CANNOT access the database directly
- You CANNOT see Gmail tokens or credentials
- Always explain data in simple, helpful terms
- Use Indian Rupee (₹) for currency

When answering questions, first call the appropriate tool(s) to get data,
then explain the results to the user in a friendly way."""
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ]
            
            # Call LLM via router (handles local/groq switching)
            response = self.llm.generate(messages, tools=self.get_available_tools())
            provider_used = response.get("provider_used")
            
            if not response["success"]:
                return {
                    "success": False,
                    "response": "I'm having trouble connecting to the AI service. Please try again.",
                    "tools_used": [],
                    "provider_used": provider_used,
                    "error": response.get("error")
                }
            
            # Step 2: Handle tool calls (may be multiple rounds)
            max_iterations = 5  # Prevent infinite loops
            iteration = 0
            
            while response.get("tool_calls") and iteration < max_iterations:
                iteration += 1
                tool_calls = response["tool_calls"]
                
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    
                    # Parse arguments
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    # Execute the tool
                    tool_result = self.execute_tool(tool_name, arguments)
                    tools_used.append(tool_name)
                    
                    # Add tool result to conversation
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result["result"] if tool_result["success"] else {"error": tool_result["error"]})
                    })
                
                # Call LLM again with tool results
                response = self.llm.generate(messages, tools=self.get_available_tools())
                provider_used = response.get("provider_used", provider_used)
                
                if not response["success"]:
                    break
            
            # Step 3: Get final response
            final_response = response.get("content", "I couldn't generate a response.")
            
            print(f"✅ Chat completed. Tools used: {tools_used}, Provider: {provider_used}")
            
            return {
                "success": True,
                "response": final_response,
                "tools_used": tools_used,
                "provider_used": provider_used,
                "error": None
            }
            
        except Exception as e:
            print(f"❌ Chat error: {str(e)}")
            return {
                "success": False,
                "response": "An error occurred while processing your request.",
                "tools_used": tools_used,
                "provider_used": provider_used,
                "error": str(e)
            }
    
    def get_llm_status(self) -> dict:
        """
        Get status of the LLM router.
        
        Returns:
            Dict with provider info and availability
        """
        return self.llm.get_status()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
# Create a single MCP server instance for the application
mcp_server = MCPServer()

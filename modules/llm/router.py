"""
LLM Router for Project LUMEN
=============================
THE SINGLE, CENTRAL SWITCH POINT for all LLM operations.

This router:
- Chooses which LLM to use based on LLM_PROVIDER config
- Handles automatic fallback (local → groq)
- Provides a unified interface for both adapters

CONFIGURATION:
- LLM_PROVIDER=local  → Use local fine-tuned LLM only
- LLM_PROVIDER=groq   → Use Groq API only
- LLM_PROVIDER=auto   → Try local first, fallback to Groq (DEFAULT)

SECURITY:
- This router only passes pre-processed MCP tool outputs to LLMs
- Raw data never reaches this layer
- Both adapters have the same security constraints
"""

import os
from dotenv import load_dotenv

from modules.llm.local_llm import LocalLLMAdapter
from modules.llm.groq_llm import GroqLLMAdapter

load_dotenv()

# =============================================================================
# THE ONE CONFIG VALUE THAT CONTROLS EVERYTHING
# =============================================================================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()
# Options: "local" | "groq" | "auto"


class LLMRouter:
    """
    Central LLM Router - The SINGLE switch point for all LLM operations.
    
    Usage:
        router = LLMRouter()
        result = router.generate(messages, tools)
    
    The router automatically:
    1. Selects the appropriate LLM based on LLM_PROVIDER
    2. Handles fallback if primary fails (in "auto" mode)
    3. Returns unified response format
    """
    
    def __init__(self):
        """Initialize router with all available adapters."""
        self.local = LocalLLMAdapter()
        self.groq = GroqLLMAdapter()
        self.provider = LLM_PROVIDER
        
        print(f"🔀 LLM Router initialized | Provider: {self.provider.upper()}")
        print(f"   Local LLM: {'✅ Available' if self.local.is_available() else '❌ Not available'}")
        print(f"   Groq API:  {'✅ Configured' if self.groq.is_available() else '❌ Not configured'}")
    
    def get_active_provider(self) -> str:
        """
        Get the currently active LLM provider.
        
        Returns:
            str: "local", "groq", or "auto"
        """
        return self.provider
    
    def get_status(self) -> dict:
        """
        Get status of all LLM adapters.
        
        Returns:
            {
                "provider": "auto",
                "local": {"available": True, "model": "..."},
                "groq": {"available": True, "model": "..."}
            }
        """
        return {
            "provider": self.provider,
            "local": {
                "available": self.local.is_available(),
                "model": self.local.model,
                "url": self.local.url
            },
            "groq": {
                "available": self.groq.is_available(),
                "model": self.groq.model
            }
        }
    
    def generate(self, messages: list, tools: list = None) -> dict:
        """
        Generate a response using the configured LLM provider.
        
        This is THE main entry point for all LLM operations.
        
        Args:
            messages: List of message dicts [{role, content}, ...]
            tools: Optional list of tool definitions for function calling
        
        Returns:
            {
                "success": True/False,
                "content": "LLM response text" or None,
                "tool_calls": [...] or None,
                "provider_used": "local" or "groq",
                "error": "message" or None
            }
        """
        
        # ==== LOCAL ONLY ====
        if self.provider == "local":
            result = self.local.generate(messages, tools)
            result["provider_used"] = "local"
            return result
        
        # ==== GROQ ONLY ====
        elif self.provider == "groq":
            result = self.groq.generate(messages, tools)
            result["provider_used"] = "groq"
            return result
        
        # ==== AUTO: Try local first, fallback to Groq ====
        else:  # "auto" is default
            # Try local LLM first
            if self.local.is_available():
                print("🔀 Trying local LLM...")
                result = self.local.generate(messages, tools)
                
                if result["success"]:
                    result["provider_used"] = "local"
                    return result
                else:
                    print(f"⚠️  Local LLM failed: {result['error']}")
            
            # Fallback to Groq
            if self.groq.is_available():
                print("🔀 Falling back to Groq...")
                result = self.groq.generate(messages, tools)
                result["provider_used"] = "groq"
                return result
            
            # Both failed
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "provider_used": None,
                "error": "No LLM available. Check local server or Groq API key."
            }
    
    def generate_simple(self, prompt: str, system_prompt: str = None) -> dict:
        """
        Simple generation without tool calling.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
        
        Returns:
            Same format as generate()
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.generate(messages, tools=None)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
# Create a single router instance for the application
# Import this in other modules: from modules.llm.router import llm_router

llm_router = LLMRouter()

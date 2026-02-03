"""
Groq LLM Adapter for Project LUMEN
===================================
Wraps Groq API as a secondary/fallback LLM.

This adapter:
- Connects to Groq's fast inference API
- Uses Llama 3.3 70B or similar models
- Supports tool calling

SECURITY CONSTRAINTS:
- NEVER send raw emails, tokens, or DB rows to Groq
- ONLY send aggregated JSON summaries from MCP tools
- This is a CLOUD service - treat all data as potentially logged

The adapter only receives pre-processed MCP tool outputs.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "30"))


class GroqLLMAdapter:
    """
    Adapter for Groq API.
    
    Responsibilities:
    1. Format messages for Groq API
    2. Handle tool calls (OpenAI-compatible format)
    3. Return responses in unified format
    
    IMPORTANT: Groq is a cloud service. Only send aggregated,
    non-sensitive data through this adapter.
    """
    
    def __init__(self):
        self.url = GROQ_API_URL
        self.model = GROQ_MODEL
        self.timeout = GROQ_TIMEOUT
        self.api_key = GROQ_API_KEY
        self.name = "groq"
    
    def is_available(self) -> bool:
        """
        Check if Groq API is configured and reachable.
        
        Returns:
            bool: True if API key is set, False otherwise
        """
        # Groq is available if API key is configured
        # We don't make a test request to avoid wasting API calls
        return bool(self.api_key and len(self.api_key) > 10)
    
    def generate(self, messages: list, tools: list = None) -> dict:
        """
        Generate a response from Groq API.
        
        Args:
            messages: List of message dicts [{role, content}, ...]
            tools: Optional list of tool definitions for function calling
        
        Returns:
            {
                "success": True/False,
                "content": "LLM response text" or None,
                "tool_calls": [...] or None,
                "error": "message" or None
            }
        """
        if not self.api_key:
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "error": "Groq API key not configured"
            }
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            # Add tools if provided (for function calling)
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                message = result["choices"][0]["message"]
                
                return {
                    "success": True,
                    "content": message.get("content"),
                    "tool_calls": message.get("tool_calls"),
                    "error": None
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "content": None,
                    "tool_calls": None,
                    "error": "Groq API authentication failed - check API key"
                }
            elif response.status_code == 429:
                return {
                    "success": False,
                    "content": None,
                    "tool_calls": None,
                    "error": "Groq API rate limit exceeded"
                }
            else:
                return {
                    "success": False,
                    "content": None,
                    "tool_calls": None,
                    "error": f"Groq API error: HTTP {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "error": "Groq API request timed out"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "error": "Could not connect to Groq API"
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "error": f"Groq API error: {str(e)}"
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

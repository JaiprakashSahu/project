"""
Local LLM Adapter for Project LUMEN
====================================
Wraps your fine-tuned local LLM for personalized financial reasoning.

This adapter:
- Connects to your local LLM server (LM Studio, Ollama, etc.)
- Supports tool calling (function calling format)
- Returns structured responses

SECURITY: This adapter only receives pre-processed MCP tool outputs.
It never sees raw database rows, Gmail tokens, or credentials.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration from environment
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://172.16.122.48:1234/v1/chat/completions")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5-coder-3b-instruct-mlx")
LOCAL_LLM_TIMEOUT = int(os.getenv("LOCAL_LLM_TIMEOUT", "30"))


class LocalLLMAdapter:
    """
    Adapter for local fine-tuned LLM.
    
    Responsibilities:
    1. Format messages for local LLM
    2. Handle tool calls
    3. Return responses in unified format
    """
    
    def __init__(self):
        self.url = LOCAL_LLM_URL
        self.model = LOCAL_LLM_MODEL
        self.timeout = LOCAL_LLM_TIMEOUT
        self.name = "local"
    
    def is_available(self) -> bool:
        """
        Check if local LLM is reachable.
        
        Returns:
            bool: True if server responds, False otherwise
        """
        try:
            # Quick health check - just try to connect
            response = requests.get(
                self.url.replace("/chat/completions", "/models"),
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def generate(self, messages: list, tools: list = None) -> dict:
        """
        Generate a response from the local LLM.
        
        Args:
            messages: List of message dicts [{role, content}, ...]
            tools: Optional list of tool definitions for function calling
        
        Returns:
            {
                "success": True/False,
                "content": "LLM response text" or None,
                "tool_calls": [...] or None,  # If LLM wants to call tools
                "error": "message" or None
            }
        """
        try:
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
                headers={"Content-Type": "application/json"},
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
            else:
                return {
                    "success": False,
                    "content": None,
                    "tool_calls": None,
                    "error": f"Local LLM error: HTTP {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "error": "Local LLM request timed out"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "error": "Could not connect to local LLM server"
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "error": f"Local LLM error: {str(e)}"
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

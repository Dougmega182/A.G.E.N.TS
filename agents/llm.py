"""
A.G.E.N.T.S. — LLM Provider abstraction.
Supports OpenAI API and Ollama for local models.
"""
import os
import json
from typing import Optional, Generator
from dotenv import load_dotenv

load_dotenv()


class LLMProvider:
    """Abstraction over LLM backends — OpenAI or Ollama."""

    def __init__(self, provider: str = "openai", model: Optional[str] = None):
        self.provider = provider
        if provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        elif provider == "ollama":
            self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            self.model = model or os.getenv("OLLAMA_MODEL", "llama3")
            self.client = None
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def chat(self, system_prompt: str, user_message: str,
             temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Send a chat message and return the response."""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content

        elif self.provider == "ollama":
            import requests
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            )
            return response.json()["message"]["content"]

    def chat_json(self, system_prompt: str, user_message: str,
                  temperature: float = 0.3) -> dict:
        """Send a chat message and parse the response as JSON."""
        json_prompt = system_prompt + "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        response = self.chat(json_prompt, user_message, temperature=temperature)
        # Try to extract JSON from the response
        response = response.strip()
        if response.startswith("```"):
            # Strip markdown code fences
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        return json.loads(response)

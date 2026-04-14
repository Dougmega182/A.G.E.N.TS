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

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "ollama")
        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        elif self.provider == "ollama":
            self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:8b")
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
            import httpx
            async def _call():
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
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
            
            import asyncio
            try:
                # If we're already in an event loop (e.g. FastAPI), we should use await
                # But for the synchronous 'chat' signature, we'll run it in a way that works.
                # Actually, I'll make the chat method itself 'async' soon.
                # For now, let's just make it a standard async-ready call.
                return asyncio.run(_call())
            except RuntimeError:
                # If loop is already running, we have a problem with this sync wrapper
                # I'll update the Agent.chat to call an async version.
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
                        "options": {"temperature": temperature, "num_predict": max_tokens}
                    }
                )
                return response.json()["message"]["content"]

    async def astream_chat(self, system_prompt: str, user_message: str,
                          temperature: float = 0.7, max_tokens: int = 2000) -> Generator[str, None, None]:
        """Stream chat tokens asynchronously (Server-Sent Events style)."""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        elif self.provider == "ollama":
            import httpx
            import json
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        }
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                            if data.get("done"):
                                break

    def chat_json(self, system_prompt: str, user_message: str,
                  temperature: float = 0.3) -> dict:
        """Send a chat message and parse the response as JSON."""
        # This remains synchronous for internal governance logic
        json_prompt = system_prompt + "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        response = self.chat(json_prompt, user_message, temperature=temperature)
        # Try to extract JSON from the response
        response = response.strip()
        if response.startswith("```"):
            # Strip markdown code fences
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        return json.loads(response)

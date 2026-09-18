import os
import logging

try:
    from groq import Groq
except ImportError:
    pass

from src.llm.config import LLM_CONFIG

logger = logging.getLogger("LLMClient")


class LLMClient:
    """Generic LLM client. Accepts messages, returns a response."""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. Responses will fail.")

        self.client = Groq()

    def chat(self, messages: list[dict]) -> str:
        """Send a list of messages to the LLM and return the response text.

        Args:
            messages: A list of message dicts, e.g.
                [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

        Returns:
            The LLM's response as a string.
        """
        try:
            completion = self.client.chat.completions.create(
                messages=messages,
                **LLM_CONFIG,
            )

            content = completion.choices[0].message.content
            return content.strip() if content else ""

        except Exception as e:
            logger.error("Error calling Groq SDK: %s", e)
            return ""

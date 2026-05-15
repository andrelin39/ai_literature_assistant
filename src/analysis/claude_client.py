"""Claude API wrapper with forced tool use and cost tracking."""
from __future__ import annotations

import anthropic

from src.analysis.exceptions import ClaudeAPIError, SchemaValidationError
from src.config import settings

# USD per million tokens
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}

_DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


class ClaudeAnalysisClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int = 2,
    ) -> None:
        self.client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model or settings.claude_model_default
        self.max_retries = max_retries

    def call_with_tool(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_description: str,
        tool_input_schema: dict,
        max_tokens: int = 4096,
    ) -> tuple[dict, dict]:
        """Call Claude and force it to use the specified tool.

        Returns:
            (tool_input_dict, usage_dict) where usage_dict has
            input_tokens, output_tokens, estimated_cost_usd.

        Raises:
            ClaudeAPIError: API call failed (auth, network, etc.)
            SchemaValidationError: No tool_use block after all attempts.
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                tools=[
                    {
                        "name": tool_name,
                        "description": tool_description,
                        "input_schema": tool_input_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.AuthenticationError as e:
            raise ClaudeAPIError(f"Authentication failed: {e}") from e
        except anthropic.APIConnectionError as e:
            raise ClaudeAPIError(f"Connection error: {e}") from e
        except anthropic.APIStatusError as e:
            raise ClaudeAPIError(f"API error {e.status_code}: {e.message}") from e

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                usage = self._compute_usage(response)
                return block.input, usage

        raise SchemaValidationError(
            f"Claude did not call tool '{tool_name}' (stop_reason={response.stop_reason!r})"
        )

    def _compute_usage(self, response: anthropic.types.Message) -> dict:
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        pricing = MODEL_PRICING.get(self.model, _DEFAULT_PRICING)
        cost = (
            input_tokens / 1_000_000 * pricing["input"]
            + output_tokens / 1_000_000 * pricing["output"]
        )
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": round(cost, 8),
        }

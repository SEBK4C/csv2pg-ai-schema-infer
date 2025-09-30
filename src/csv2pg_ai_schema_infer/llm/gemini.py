"""Google Gemini LLM provider implementation."""

import asyncio
import json
import time

import google.generativeai as genai

from ..types import ColumnChunk, InferredType
from ..utils.logger import logger
from ..utils.validation import validate_inferred_type
from .base import LLMProvider


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider for type inference."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-pro",
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: int = 5,
    ):
        """
        Initialize Gemini provider.

        Args:
            api_key: Gemini API key
            model: Model name
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        if not api_key:
            raise ValueError("Gemini API key is required")

        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        # Configure Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

        logger.debug(f"Initialized Gemini provider with model: {model}")

    def _build_prompt(self, chunk: ColumnChunk) -> str:
        """Build prompt for type inference."""
        # Format sample data
        sample_str = json.dumps(chunk.sample_data[:20], indent=2)  # Limit to 20 rows

        prompt = f"""You are a PostgreSQL database schema expert. Analyze these CSV columns and suggest optimal PostgreSQL data types.

Columns to analyze: {', '.join(chunk.columns)}

Sample data (first 20 rows):
{sample_str}

For each column, analyze the data and determine:
1. The most appropriate PostgreSQL type
2. Whether the column should be nullable
3. Any constraints (PRIMARY KEY, UNIQUE, etc.)
4. Your reasoning

Return a JSON array with this exact structure:
[
  {{
    "column_name": "column_name_here",
    "postgresql_type": "postgresql_type_here",
    "confidence": "high|medium|low",
    "reasoning": "brief explanation",
    "nullable": true|false,
    "constraints": ["CONSTRAINT1", "CONSTRAINT2"],
    "cast_rule": null
  }}
]

PostgreSQL type guidelines:
- Use INTEGER for small whole numbers, BIGINT for large ones
- Use NUMERIC(precision, scale) for decimals requiring exact precision
- Use REAL or DOUBLE PRECISION for floating point
- Use VARCHAR(n) for bounded strings, TEXT for unbounded
- Use TIMESTAMP WITH TIME ZONE (timestamptz) for timestamps
- Use DATE for dates without time
- Use UUID for UUID patterns
- Use BOOLEAN for true/false values
- Use JSONB for JSON data
- Consider NULL percentage when setting nullable

Respond ONLY with the JSON array, no additional text."""

        return prompt

    def _parse_response(self, response_text: str, chunk: ColumnChunk) -> list[InferredType]:
        """Parse and validate Gemini response."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]  # Remove ```json
            if text.startswith("```"):
                text = text[3:]  # Remove ```
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            # Parse JSON
            data = json.loads(text)

            if not isinstance(data, list):
                raise ValueError("Response must be a JSON array")

            # Validate each type
            inferred_types = []
            for item in data:
                try:
                    inferred_type = validate_inferred_type(item)
                    inferred_types.append(inferred_type)
                except Exception as e:
                    logger.warning(
                        f"Failed to validate type for column {item.get('column_name')}: {e}"
                    )

            # Ensure we have types for all columns
            if len(inferred_types) != len(chunk.columns):
                logger.warning(
                    f"Expected {len(chunk.columns)} types, got {len(inferred_types)}"
                )

            return inferred_types

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to parse response: {e}") from e

    async def infer_types(self, chunk: ColumnChunk) -> list[InferredType]:
        """
        Infer types asynchronously.

        Args:
            chunk: Column chunk

        Returns:
            List of inferred types
        """
        # Run sync version in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.infer_types_sync, chunk)

    def infer_types_sync(self, chunk: ColumnChunk) -> list[InferredType]:
        """
        Infer types synchronously with retry logic.

        Args:
            chunk: Column chunk

        Returns:
            List of inferred types

        Raises:
            Exception: If all retries fail
        """
        prompt = self._build_prompt(chunk)

        last_error = None
        for attempt in range(self.retry_attempts):
            try:
                logger.debug(
                    f"Calling Gemini API for chunk {chunk.chunk_id + 1}/"
                    f"{chunk.total_chunks} (attempt {attempt + 1})"
                )

                # Generate response
                response = self.model.generate_content(prompt)

                if not response or not response.text:
                    raise ValueError("Empty response from Gemini API")

                # Parse and validate response
                inferred_types = self._parse_response(response.text, chunk)

                logger.info(
                    f"Successfully inferred types for chunk {chunk.chunk_id + 1}/"
                    f"{chunk.total_chunks} ({len(inferred_types)} columns)"
                )

                return inferred_types

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Gemini API call failed (attempt {attempt + 1}/"
                    f"{self.retry_attempts}): {e}"
                )

                if attempt < self.retry_attempts - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2**attempt)
                    logger.debug(f"Retrying in {delay} seconds...")
                    time.sleep(delay)

        # All retries failed
        raise Exception(
            f"Failed to infer types after {self.retry_attempts} attempts: {last_error}"
        )

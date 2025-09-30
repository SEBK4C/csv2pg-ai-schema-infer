"""Google Gemini LLM provider implementation."""

import asyncio
import time

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from pydantic import BaseModel, Field

from ..types import ColumnChunk, InferredType, ConfidenceLevel
from ..utils.logger import logger
from .base import LLMProvider


# Simplified schema for API (without defaults that Gemini doesn't support)
class InferredTypeAPI(BaseModel):
    """Simplified InferredType for Gemini API (no defaults)."""
    column_name: str
    pg_type: str
    confidence: str  # Use string instead of enum for API
    reasoning: str
    nullable: bool
    constraints: list[str]
    cast_rule: str | None


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
        """Build prompt for type inference using structured output."""
        import json

        # Format sample data (limit to 20 rows for token efficiency)
        sample_str = json.dumps(chunk.sample_data[:20], indent=2)

        prompt = f"""You are a PostgreSQL database schema expert. Analyze these CSV columns and suggest optimal PostgreSQL data types.

Columns to analyze: {', '.join(chunk.columns)}

Sample data (first 20 rows):
{sample_str}

For each column, determine:
1. The most appropriate PostgreSQL type (use exact type names)
2. Whether the column should be nullable (true/false)
3. Confidence level in your assessment (HIGH, MEDIUM, or LOW)
4. Brief reasoning for your type choice
5. Any constraints if applicable
6. Cast rule if needed (usually null)

PostgreSQL type guidelines:
- Use "integer" for small whole numbers (-2B to 2B), "bigint" for large ones
- Use "numeric" for decimals requiring exact precision (money, financial data)
- Use "real" or "double precision" for floating point
- Use "text" for unbounded strings, "varchar(n)" only if you know the limit
- Use "timestamptz" for timestamps with timezone
- Use "date" for dates without time
- Use "uuid" for UUID patterns
- Use "boolean" for true/false values
- Use "jsonb" for JSON data
- Set nullable=true if any NULL values exist in the sample

Analyze each column carefully and provide accurate type recommendations."""

        return prompt

    def _validate_response(self, inferred_types: list[InferredType], chunk: ColumnChunk) -> list[InferredType]:
        """Validate and sanitize the structured response."""
        # Ensure we have types for all columns
        if len(inferred_types) != len(chunk.columns):
            logger.warning(
                f"Expected {len(chunk.columns)} types, got {len(inferred_types)}"
            )

        # Log any low confidence types
        for inferred in inferred_types:
            if inferred.confidence.value == "LOW":
                logger.warning(
                    f"Low confidence type for column {inferred.column_name}: "
                    f"{inferred.pg_type} - {inferred.reasoning}"
                )

        return inferred_types

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
        Infer types synchronously with retry logic using structured output.

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

                # Use structured output with simplified Pydantic schema
                generation_config = GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=list[InferredTypeAPI],
                )

                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                if not response or not response.text:
                    raise ValueError("Empty response from Gemini API")

                # Parse the structured JSON response
                import json
                response_data = json.loads(response.text)

                # Convert to InferredType objects (with proper enum conversion)
                inferred_types = []
                for item in response_data:
                    # Convert confidence string to enum
                    confidence_str = item.get("confidence", "MEDIUM").upper()
                    if confidence_str not in ["HIGH", "MEDIUM", "LOW"]:
                        confidence_str = "MEDIUM"

                    inferred_types.append(InferredType(
                        column_name=item["column_name"],
                        pg_type=item["pg_type"],
                        confidence=ConfidenceLevel[confidence_str],
                        reasoning=item["reasoning"],
                        nullable=item["nullable"],
                        constraints=item.get("constraints", []),
                        cast_rule=item.get("cast_rule"),
                    ))

                if not inferred_types:
                    raise ValueError("Parsed response is empty")

                # Validate response
                inferred_types = self._validate_response(inferred_types, chunk)

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

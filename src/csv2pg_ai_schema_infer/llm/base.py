"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any

from ..types import ColumnChunk, InferredType


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def infer_types(
        self,
        chunk: ColumnChunk,
    ) -> list[InferredType]:
        """
        Infer PostgreSQL types for columns in a chunk.

        Args:
            chunk: Column chunk with sample data

        Returns:
            List of inferred types for each column

        Raises:
            Exception: If API call fails
        """
        pass

    @abstractmethod
    def infer_types_sync(
        self,
        chunk: ColumnChunk,
    ) -> list[InferredType]:
        """
        Synchronous version of infer_types.

        Args:
            chunk: Column chunk with sample data

        Returns:
            List of inferred types for each column

        Raises:
            Exception: If API call fails
        """
        pass
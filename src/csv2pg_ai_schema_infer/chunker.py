"""Column chunking module for processing wide CSVs."""

from typing import Any

from .sampler import sample_csv_columns
from .types import ColumnChunk, CSVSample
from .utils.logger import logger


def chunk_columns(
    sample: CSVSample,
    chunk_size: int = 20,
) -> list[ColumnChunk]:
    """
    Split columns into chunks for batch processing.

    Args:
        sample: CSV sample
        chunk_size: Maximum number of columns per chunk

    Returns:
        List of column chunks with metadata
    """
    columns = sample.headers
    total_columns = len(columns)

    if total_columns == 0:
        raise ValueError("No columns to chunk")

    # Calculate number of chunks
    total_chunks = (total_columns + chunk_size - 1) // chunk_size

    chunks = []
    for i in range(total_chunks):
        start_idx = i * chunk_size
        end_idx = min(start_idx + chunk_size, total_columns)

        chunk_columns_list = columns[start_idx:end_idx]

        # Extract sample data for these columns
        chunk_data = sample_csv_columns(sample, chunk_columns_list)

        chunk = ColumnChunk(
            chunk_id=i,
            total_chunks=total_chunks,
            columns=chunk_columns_list,
            sample_data=chunk_data,
        )
        chunks.append(chunk)

    logger.debug(
        f"Split {total_columns} columns into {total_chunks} chunks "
        f"(size: {chunk_size})"
    )

    return chunks


def chunk_columns_smart(
    sample: CSVSample,
    chunk_size: int = 20,
) -> list[ColumnChunk]:
    """
    Split columns into chunks, keeping related columns together.

    Groups columns by naming patterns (e.g., 'user_*', 'address_*')
    and tries to keep groups together when possible.

    Args:
        sample: CSV sample
        chunk_size: Maximum number of columns per chunk

    Returns:
        List of column chunks with metadata
    """
    columns = sample.headers
    total_columns = len(columns)

    if total_columns == 0:
        raise ValueError("No columns to chunk")

    # Group columns by prefix (before first underscore)
    groups: dict[str, list[str]] = {}
    for col in columns:
        prefix = col.split("_")[0] if "_" in col else "other"
        if prefix not in groups:
            groups[prefix] = []
        groups[prefix].append(col)

    # Build chunks, keeping groups together when possible
    chunks_data: list[list[str]] = []
    current_chunk: list[str] = []

    for prefix, group_columns in groups.items():
        # If adding this group exceeds chunk size
        if len(current_chunk) + len(group_columns) > chunk_size:
            # If current chunk is not empty, save it
            if current_chunk:
                chunks_data.append(current_chunk)
                current_chunk = []

            # If group itself is larger than chunk size, split it
            if len(group_columns) > chunk_size:
                for i in range(0, len(group_columns), chunk_size):
                    chunk_group = group_columns[i : i + chunk_size]
                    chunks_data.append(chunk_group)
            else:
                current_chunk = group_columns.copy()
        else:
            current_chunk.extend(group_columns)

    # Add remaining columns
    if current_chunk:
        chunks_data.append(current_chunk)

    # Convert to ColumnChunk objects
    total_chunks = len(chunks_data)
    chunks = []

    for i, chunk_columns_list in enumerate(chunks_data):
        chunk_data = sample_csv_columns(sample, chunk_columns_list)

        chunk = ColumnChunk(
            chunk_id=i,
            total_chunks=total_chunks,
            columns=chunk_columns_list,
            sample_data=chunk_data,
        )
        chunks.append(chunk)

    logger.debug(
        f"Smart-chunked {total_columns} columns into {total_chunks} chunks "
        f"(grouped by prefix)"
    )

    return chunks
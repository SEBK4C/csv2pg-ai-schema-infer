"""CSV sampling and analysis module."""

from pathlib import Path
from typing import Any

import charset_normalizer
import polars as pl

from .types import CSVProperties, CSVSample
from .utils.logger import logger


def detect_encoding(file_path: Path) -> str:
    """
    Detect file encoding using charset-normalizer.

    Args:
        file_path: Path to CSV file

    Returns:
        Detected encoding (e.g., 'utf-8', 'latin-1')
    """
    with open(file_path, "rb") as f:
        # Read first 100KB for detection
        raw_data = f.read(102400)

    result = charset_normalizer.from_bytes(raw_data).best()
    if result is None:
        logger.warning("Could not detect encoding, defaulting to utf-8")
        return "utf-8"

    encoding = result.encoding
    logger.debug(f"Detected encoding: {encoding}")
    return encoding


def detect_csv_properties(
    file_path: Path, encoding: str | None = None
) -> CSVProperties:
    """
    Detect CSV file properties (delimiter, encoding, etc.).

    Args:
        file_path: Path to CSV file
        encoding: Optional encoding override

    Returns:
        CSV properties
    """
    if encoding is None:
        encoding = detect_encoding(file_path)

    # Try different delimiters
    delimiters = [",", "\t", "|", ";"]

    for delimiter in delimiters:
        try:
            # Try to read first few rows with this delimiter
            df = pl.read_csv(
                file_path,
                separator=delimiter,
                encoding=encoding,
                n_rows=5,
                ignore_errors=True,
            )

            # Check if we got reasonable column count (>1 means delimiter works)
            if df.shape[1] > 1:
                logger.debug(
                    f"Detected delimiter: '{delimiter}' "
                    f"({df.shape[1]} columns detected)"
                )

                # Get total row count (approximate for large files)
                try:
                    full_df = pl.scan_csv(
                        file_path, separator=delimiter, encoding=encoding
                    )
                    row_count = full_df.select(pl.count()).collect().item()
                except Exception:
                    row_count = None

                return CSVProperties(
                    delimiter=delimiter,
                    encoding=encoding,
                    quote_char='"',
                    has_header=True,
                    row_count=row_count,
                    column_count=df.shape[1],
                )
        except Exception as e:
            logger.debug(f"Failed to parse with delimiter '{delimiter}': {e}")
            continue

    # Default fallback
    logger.warning("Could not detect delimiter, defaulting to comma")
    return CSVProperties(
        delimiter=",",
        encoding=encoding,
        quote_char='"',
        has_header=True,
        row_count=None,
        column_count=0,
    )


def sample_csv(
    path: Path,
    n_rows: int = 100,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> CSVSample:
    """
    Sample CSV file and extract headers and sample rows.

    Args:
        path: Path to CSV file
        n_rows: Number of rows to sample
        encoding: Optional encoding override
        delimiter: Optional delimiter override

    Returns:
        CSV sample with headers and data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is empty or malformed
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    logger.info(f"Sampling CSV file: {path}")

    # Detect properties if not provided
    properties = detect_csv_properties(path, encoding)

    if delimiter:
        properties.delimiter = delimiter
    if encoding:
        properties.encoding = encoding

    # Read sample with polars
    try:
        df = pl.read_csv(
            path,
            separator=properties.delimiter,
            encoding=properties.encoding,
            n_rows=n_rows,
            ignore_errors=True,
        )
    except Exception as e:
        raise ValueError(f"Failed to read CSV file: {e}") from e

    if df.is_empty():
        raise ValueError("CSV file is empty")

    # Extract headers
    headers = df.columns

    # Convert to list of dicts for easier processing
    rows = df.to_dicts()

    logger.info(
        f"Sampled {len(rows)} rows, {len(headers)} columns from {path.name}"
    )

    return CSVSample(
        path=path,
        properties=properties,
        headers=headers,
        rows=rows,
        sample_size=len(rows),
    )


def sample_csv_columns(sample: CSVSample, column_names: list[str]) -> list[dict[str, Any]]:
    """
    Extract specific columns from CSV sample.

    Args:
        sample: CSV sample
        column_names: List of column names to extract

    Returns:
        List of dicts with only specified columns
    """
    filtered_rows = []
    for row in sample.rows:
        filtered_row = {col: row.get(col) for col in column_names if col in row}
        filtered_rows.append(filtered_row)

    return filtered_rows

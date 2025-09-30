"""Type inference orchestration module."""

import asyncio
import re

from .chunker import chunk_columns, chunk_columns_smart
from .llm.base import LLMProvider
from .types import (
    ColumnSample,
    ColumnSchema,
    ConfidenceLevel,
    CSVSample,
    InferredType,
    TableSchema,
)
from .utils.logger import logger

# PostgreSQL reserved keywords that need prefixing
POSTGRES_RESERVED_KEYWORDS = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "asymmetric",
    "both", "case", "cast", "check", "collate", "column", "constraint", "create",
    "current_catalog", "current_date", "current_role", "current_time",
    "current_timestamp", "current_user", "default", "deferrable", "desc", "distinct",
    "do", "else", "end", "except", "false", "fetch", "for", "foreign", "from",
    "grant", "group", "having", "in", "initially", "intersect", "into", "lateral",
    "leading", "limit", "localtime", "localtimestamp", "not", "null", "offset",
    "on", "only", "or", "order", "placing", "primary", "references", "returning",
    "select", "session_user", "some", "symmetric", "table", "then", "to", "trailing",
    "true", "union", "unique", "user", "using", "variadic", "when", "where", "window",
    "with"
}


def sanitize_column_name(name: str) -> str:
    """
    Sanitize column name for PostgreSQL compatibility.

    - Converts to lowercase
    - Replaces dots and special characters with underscores
    - Ensures name starts with letter or underscore
    - Handles PostgreSQL reserved keywords

    Args:
        name: Original column name

    Returns:
        Sanitized column name safe for PostgreSQL
    """
    # Convert to lowercase
    name = name.lower()

    # Replace dots and special characters with underscores
    # Keep only alphanumeric and underscore
    name = re.sub(r'[^a-z0-9_]', '_', name)

    # Remove consecutive underscores
    name = re.sub(r'_+', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    # Ensure starts with letter or underscore (not digit)
    if name and name[0].isdigit():
        name = f'col_{name}'

    # Handle empty names
    if not name:
        name = 'unnamed_column'

    # Handle reserved keywords
    if name in POSTGRES_RESERVED_KEYWORDS:
        name = f'{name}_col'

    return name


def heuristic_type_inference(column: ColumnSample) -> InferredType:
    """
    Fallback heuristic type inference based on pattern matching.

    Args:
        column: Column sample

    Returns:
        Inferred type
    """
    # Sanitize column name
    sanitized_name = sanitize_column_name(column.name)

    # Get non-null values
    non_null_values = [v for v in column.values if v is not None and str(v).strip()]

    if not non_null_values:
        return InferredType(
            column_name=sanitized_name,
            pg_type="text",
            confidence=ConfidenceLevel.LOW,
            reasoning="All values are null, defaulting to text",
            nullable=True,
        )

    # Sample first 100 values for analysis
    sample_values = non_null_values[:100]
    str_values = [str(v).strip() for v in sample_values]

    # UUID pattern
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    if all(uuid_pattern.match(v) for v in str_values):
        return InferredType(
            column_name=sanitized_name,
            pg_type="uuid",
            confidence=ConfidenceLevel.HIGH,
            reasoning="All values match UUID pattern",
            nullable=column.null_percentage > 0,
        )

    # Boolean pattern
    boolean_values = {"true", "false", "t", "f", "yes", "no", "y", "n", "1", "0"}
    if all(v.lower() in boolean_values for v in str_values):
        return InferredType(
            column_name=sanitized_name,
            pg_type="boolean",
            confidence=ConfidenceLevel.HIGH,
            reasoning="All values are boolean-like",
            nullable=column.null_percentage > 0,
        )

    # Check for currency/financial columns by name
    is_currency_column = any(keyword in sanitized_name for keyword in
                             ['usd', 'price', 'value', 'amount', 'total', 'funding', 'valuation'])

    # Integer pattern
    try:
        int_values = [int(v) for v in str_values]
        max_val = max(int_values)
        min_val = min(int_values)

        # Check if fits in integer or needs bigint
        if -2147483648 <= min_val <= 2147483647 and -2147483648 <= max_val <= 2147483647:
            pg_type = "integer"
        else:
            pg_type = "bigint"

        return InferredType(
            column_name=sanitized_name,
            pg_type=pg_type,
            confidence=ConfidenceLevel.HIGH,
            reasoning=f"All values are integers (range: {min_val} to {max_val})",
            nullable=column.null_percentage > 0,
        )
    except (ValueError, TypeError):
        pass

    # Decimal/numeric pattern
    try:
        float_values = [float(v) for v in str_values]
        # Check if any value has decimal places
        has_decimals = any(v != int(v) for v in float_values if not (v != v))  # Skip NaN

        # Force numeric for currency columns or if decimals detected
        if is_currency_column or has_decimals:
            return InferredType(
                column_name=sanitized_name,
                pg_type="numeric",
                confidence=ConfidenceLevel.HIGH,
                reasoning="Numeric values with decimal precision (or currency column)",
                nullable=column.null_percentage > 0,
            )

        return InferredType(
            column_name=sanitized_name,
            pg_type="numeric",
            confidence=ConfidenceLevel.MEDIUM,
            reasoning="All values are numeric",
            nullable=column.null_percentage > 0,
        )
    except (ValueError, TypeError):
        pass

    # Date pattern (YYYY-MM-DD)
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if all(date_pattern.match(v) for v in str_values):
        return InferredType(
            column_name=sanitized_name,
            pg_type="date",
            confidence=ConfidenceLevel.HIGH,
            reasoning="All values match date pattern (YYYY-MM-DD)",
            nullable=column.null_percentage > 0,
        )

    # Timestamp pattern (ISO 8601)
    timestamp_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    )
    if all(timestamp_pattern.match(v) for v in str_values):
        return InferredType(
            column_name=sanitized_name,
            pg_type="timestamptz",
            confidence=ConfidenceLevel.HIGH,
            reasoning="All values match timestamp pattern",
            nullable=column.null_percentage > 0,
        )

    # Email pattern
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if all(email_pattern.match(v) for v in str_values):
        return InferredType(
            column_name=sanitized_name,
            pg_type="text",
            confidence=ConfidenceLevel.MEDIUM,
            reasoning="All values match email pattern",
            nullable=column.null_percentage > 0,
        )

    # Default to text
    max_length = max(len(v) for v in str_values)
    if max_length < 255:
        pg_type = f"varchar({max_length + 50})"  # Add buffer
        reasoning = f"String values with max length {max_length}"
    else:
        pg_type = "text"
        reasoning = f"String values with max length {max_length}"

    return InferredType(
        column_name=sanitized_name,
        pg_type=pg_type,
        confidence=ConfidenceLevel.MEDIUM,
        reasoning=reasoning,
        nullable=column.null_percentage > 0,
    )


def build_column_samples(sample: CSVSample) -> list[ColumnSample]:
    """
    Build column samples from CSV sample.

    Args:
        sample: CSV sample

    Returns:
        List of column samples
    """
    column_samples = []

    for col_name in sample.headers:
        # Sanitize column name for PostgreSQL
        sanitized_name = sanitize_column_name(col_name)

        values = [row.get(col_name) for row in sample.rows]
        null_count = sum(1 for v in values if v is None or str(v).strip() == "")

        column_samples.append(
            ColumnSample(
                name=sanitized_name,  # Use sanitized name
                values=values,
                null_count=null_count,
                total_count=len(values),
            )
        )

    return column_samples


async def infer_schema_async(
    sample: CSVSample,
    provider: LLMProvider,
    chunk_size: int = 20,
    use_smart_chunking: bool = True,
    use_fallback: bool = True,
) -> TableSchema:
    """
    Infer table schema asynchronously using LLM provider.

    Args:
        sample: CSV sample
        provider: LLM provider
        chunk_size: Columns per chunk
        use_smart_chunking: Use smart chunking to group related columns
        use_fallback: Use heuristic fallback if LLM fails

    Returns:
        Complete table schema
    """
    logger.info(f"Starting type inference for {len(sample.headers)} columns")

    # Chunk columns
    if use_smart_chunking:
        chunks = chunk_columns_smart(sample, chunk_size)
    else:
        chunks = chunk_columns(sample, chunk_size)

    logger.info(f"Processing {len(chunks)} column chunks")

    # Process chunks in parallel
    tasks = [provider.infer_types(chunk) for chunk in chunks]

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"Failed to infer types with LLM: {e}")
        if use_fallback:
            logger.info("Falling back to heuristic inference")
            return infer_schema_heuristic(sample)
        raise

    # Merge results
    all_inferred_types: list[InferredType] = []
    failed_chunks = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Chunk {i} failed: {result}")
            failed_chunks.append(chunks[i])
        else:
            all_inferred_types.extend(result)

    # Handle failed chunks with heuristic fallback
    if failed_chunks and use_fallback:
        logger.info(f"Using heuristic fallback for {len(failed_chunks)} failed chunks")
        column_samples = build_column_samples(sample)
        sample_map = {cs.name: cs for cs in column_samples}

        for chunk in failed_chunks:
            for col_name in chunk.columns:
                if col_name in sample_map:
                    inferred = heuristic_type_inference(sample_map[col_name])
                    all_inferred_types.append(inferred)

    # Convert to schema
    columns = []
    for inferred in all_inferred_types:
        col_schema = ColumnSchema(
            name=inferred.column_name,
            pg_type=inferred.pg_type,
            nullable=inferred.nullable,
            constraints=inferred.constraints,
            cast_rule=inferred.cast_rule,
        )
        columns.append(col_schema)

    # Detect primary key candidate (DO NOT add to constraints yet - will be in AFTER LOAD)
    # Priority: identifier_uuid > uuid > id > *_id columns
    primary_key = None
    pk_candidates = []

    for col in columns:
        col_lower = col.name.lower()
        if col.pg_type == "uuid":
            # Prioritize identifier_uuid and similar
            if "identifier" in col_lower and "uuid" in col_lower:
                pk_candidates.append((0, col.name))  # Highest priority
            elif col_lower == "uuid":
                pk_candidates.append((1, col.name))
            elif "uuid" in col_lower:
                pk_candidates.append((2, col.name))
        elif col_lower == "id":
            pk_candidates.append((3, col.name))
        elif col_lower.endswith("_id") and col.pg_type in ("integer", "bigint"):
            pk_candidates.append((4, col.name))

    # Select the highest priority candidate
    if pk_candidates:
        pk_candidates.sort(key=lambda x: x[0])
        primary_key = pk_candidates[0][1]
        logger.info(f"Selected primary key: {primary_key}")

    # DO NOT add PRIMARY KEY to column constraints
    # It will be added in AFTER LOAD section for better performance

    # Generate table name from file name
    table_name = sanitize_column_name(sample.path.stem)

    schema = TableSchema(
        table_name=table_name,
        columns=columns,
        primary_key=primary_key,
    )

    logger.info(
        f"Schema inference complete: {len(columns)} columns, "
        f"primary_key={primary_key}"
    )

    return schema


def infer_schema_sync(
    sample: CSVSample,
    provider: LLMProvider,
    chunk_size: int = 20,
    use_smart_chunking: bool = True,
    use_fallback: bool = True,
) -> TableSchema:
    """
    Synchronous version of infer_schema_async.

    Args:
        sample: CSV sample
        provider: LLM provider
        chunk_size: Columns per chunk
        use_smart_chunking: Use smart chunking
        use_fallback: Use heuristic fallback if LLM fails

    Returns:
        Complete table schema
    """
    return asyncio.run(
        infer_schema_async(sample, provider, chunk_size, use_smart_chunking, use_fallback)
    )


def infer_schema_heuristic(sample: CSVSample) -> TableSchema:
    """
    Infer schema using only heuristics (no LLM).

    Args:
        sample: CSV sample

    Returns:
        Table schema
    """
    logger.info("Using heuristic-only inference")

    column_samples = build_column_samples(sample)
    columns = []

    for col_sample in column_samples:
        inferred = heuristic_type_inference(col_sample)
        col_schema = ColumnSchema(
            name=inferred.column_name,
            pg_type=inferred.pg_type,
            nullable=inferred.nullable,
            constraints=inferred.constraints,
            cast_rule=inferred.cast_rule,
        )
        columns.append(col_schema)

    # Detect primary key candidate (DO NOT add to constraints - will be in AFTER LOAD)
    primary_key = None
    pk_candidates = []

    for col in columns:
        col_lower = col.name.lower()
        if col.pg_type == "uuid":
            if "identifier" in col_lower and "uuid" in col_lower:
                pk_candidates.append((0, col.name))
            elif col_lower == "uuid":
                pk_candidates.append((1, col.name))
            elif "uuid" in col_lower:
                pk_candidates.append((2, col.name))
        elif col_lower == "id":
            pk_candidates.append((3, col.name))
        elif col_lower.endswith("_id") and col.pg_type in ("integer", "bigint"):
            pk_candidates.append((4, col.name))

    if pk_candidates:
        pk_candidates.sort(key=lambda x: x[0])
        primary_key = pk_candidates[0][1]
        logger.info(f"Selected primary key: {primary_key}")

    # Generate table name
    table_name = sanitize_column_name(sample.path.stem)

    return TableSchema(
        table_name=table_name,
        columns=columns,
        primary_key=primary_key,
    )

#!/usr/bin/env python3
"""
Validation script to compare Gemini AI-inferred schema with reference schema.

This script:
1. Runs the CSV2PG inference on organizations.csv
2. Parses the reference Compare_Example.load file
3. Compares data types column-by-column
4. Outputs a human-readable comparison report
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from csv2pg_ai_schema_infer.config import Config
from csv2pg_ai_schema_infer.llm.gemini import GeminiProvider
from csv2pg_ai_schema_infer.sampler import sample_csv
from csv2pg_ai_schema_infer.inference import infer_schema_sync


def parse_pgloader_schema(pgloader_file: Path) -> Dict[str, str]:
    """
    Parse a pgloader .load file and extract column name -> PostgreSQL type mappings.

    Returns:
        Dictionary mapping column names to their PostgreSQL types
    """
    with open(pgloader_file, 'r') as f:
        content = f.read()

    # Extract the CREATE TABLE section
    create_table_match = re.search(
        r'\$\$ CREATE TABLE \w+ \((.*?)\); \$\$',
        content,
        re.DOTALL | re.MULTILINE
    )

    if not create_table_match:
        raise ValueError("Could not find CREATE TABLE statement in pgloader file")

    table_def = create_table_match.group(1)

    # Parse column definitions
    column_pattern = re.compile(
        r'^\s*(\w+)\s+((?:(?:var)?char|text|integer|bigint|numeric|date|uuid|timestamptz|boolean)(?:\([^)]+\))?)',
        re.MULTILINE | re.IGNORECASE
    )

    columns = {}
    for match in column_pattern.finditer(table_def):
        col_name = match.group(1).strip().lower()
        col_type = match.group(2).strip().lower()
        columns[col_name] = col_type

    return columns


def normalize_type(pg_type: str) -> str:
    """
    Normalize PostgreSQL type for comparison.

    Examples:
    - "VARCHAR(100)" -> "varchar"
    - "TIMESTAMP WITH TIME ZONE" -> "timestamptz"
    - "DOUBLE PRECISION" -> "double precision"
    """
    pg_type = pg_type.lower().strip()

    # Remove precision/scale specifications
    pg_type = re.sub(r'\([^)]+\)', '', pg_type)

    # Normalize common aliases
    type_aliases = {
        'timestamp with time zone': 'timestamptz',
        'timestamp without time zone': 'timestamp',
        'int': 'integer',
        'int4': 'integer',
        'int8': 'bigint',
        'float8': 'double precision',
        'float4': 'real',
        'bool': 'boolean',
    }

    return type_aliases.get(pg_type.strip(), pg_type.strip())


def compare_types(inferred_type: str, reference_type: str) -> Tuple[bool, str]:
    """
    Compare two PostgreSQL types and determine if they match.

    Returns:
        (is_match, reason)
    """
    norm_inferred = normalize_type(inferred_type)
    norm_reference = normalize_type(reference_type)

    # Exact match
    if norm_inferred == norm_reference:
        return True, "Exact match"

    # Compatible numeric types
    numeric_types = {'integer', 'bigint', 'numeric', 'real', 'double precision'}
    if norm_inferred in numeric_types and norm_reference in numeric_types:
        # Allow some flexibility in numeric types
        if {norm_inferred, norm_reference} <= {'integer', 'bigint'}:
            return True, "Compatible integer types"
        if {norm_inferred, norm_reference} <= {'numeric', 'real', 'double precision'}:
            return True, "Compatible decimal types"

    # Text types are generally compatible
    text_types = {'text', 'varchar', 'character varying'}
    if norm_inferred in text_types and norm_reference in text_types:
        return True, "Compatible text types"

    return False, f"Type mismatch: {inferred_type} vs {reference_type}"


def generate_comparison_report(
    inferred_schema: Dict[str, str],
    reference_schema: Dict[str, str],
    output_file: Path
) -> Tuple[int, int, int]:
    """
    Generate a human-readable comparison report.

    Returns:
        (matches, mismatches, missing)
    """
    all_columns = set(inferred_schema.keys()) | set(reference_schema.keys())

    matches = 0
    mismatches = 0
    missing = 0

    lines = []
    lines.append("=" * 100)
    lines.append("SCHEMA COMPARISON REPORT: Gemini AI vs Reference")
    lines.append("=" * 100)
    lines.append("")

    # Sort columns alphabetically for easier reading
    for col_name in sorted(all_columns):
        inferred_type = inferred_schema.get(col_name)
        reference_type = reference_schema.get(col_name)

        if inferred_type is None:
            lines.append(f"❌ MISSING: {col_name}")
            lines.append(f"   Reference: {reference_type}")
            lines.append(f"   Inferred:  NOT FOUND")
            lines.append("")
            missing += 1
        elif reference_type is None:
            lines.append(f"⚠️  EXTRA: {col_name}")
            lines.append(f"   Reference: NOT IN REFERENCE")
            lines.append(f"   Inferred:  {inferred_type}")
            lines.append("")
            missing += 1
        else:
            is_match, reason = compare_types(inferred_type, reference_type)

            if is_match:
                lines.append(f"✅ MATCH: {col_name}")
                lines.append(f"   Reference: {reference_type}")
                lines.append(f"   Inferred:  {inferred_type}")
                lines.append(f"   Reason:    {reason}")
                lines.append("")
                matches += 1
            else:
                lines.append(f"❌ MISMATCH: {col_name}")
                lines.append(f"   Reference: {reference_type}")
                lines.append(f"   Inferred:  {inferred_type}")
                lines.append(f"   Reason:    {reason}")
                lines.append("")
                mismatches += 1

    # Summary
    lines.append("=" * 100)
    lines.append("SUMMARY")
    lines.append("=" * 100)
    lines.append(f"Total Columns:   {len(all_columns)}")
    lines.append(f"✅ Matches:      {matches} ({matches/len(all_columns)*100:.1f}%)")
    lines.append(f"❌ Mismatches:   {mismatches} ({mismatches/len(all_columns)*100:.1f}%)")
    lines.append(f"⚠️  Missing:      {missing} ({missing/len(all_columns)*100:.1f}%)")
    lines.append("=" * 100)

    # Write to file
    report_content = "\n".join(lines)
    output_file.write_text(report_content)

    # Also print to console
    print(report_content)

    return matches, mismatches, missing


def main():
    """Main validation function."""

    # Paths
    project_root = Path(__file__).parent.parent
    csv_file = Path("/root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv")
    reference_file = project_root / "Compare_Example.load"
    output_file = project_root / "schema_comparison_report.txt"

    print("=" * 100)
    print("CSV2PG Schema Validation Test")
    print("=" * 100)
    print(f"CSV File:       {csv_file}")
    print(f"Reference File: {reference_file}")
    print(f"Output File:    {output_file}")
    print("=" * 100)
    print()

    # Step 1: Parse reference schema
    print("📖 Step 1: Parsing reference schema from Compare_Example.load...")
    reference_schema = parse_pgloader_schema(reference_file)
    print(f"   Found {len(reference_schema)} columns in reference schema")
    print()

    # Step 2: Load config and run inference
    print("🤖 Step 2: Running Gemini AI inference on organizations.csv...")
    config = Config()

    # Sample CSV
    print("   Sampling CSV file...")
    sample = sample_csv(
        path=csv_file,
        n_rows=config.sampling.rows,
        encoding=config.sampling.encoding,
    )
    print(f"   Sampled {len(sample.rows)} rows, {len(sample.headers)} columns")

    # Initialize Gemini provider
    print(f"   Initializing Gemini provider (model: {config.llm.model})...")
    provider = GeminiProvider(
        api_key=config.gemini_api_key,
        model=config.llm.model,
        timeout=config.llm.timeout,
        retry_attempts=config.llm.retry_attempts,
    )

    # Run inference
    print("   Running type inference (this may take a minute)...")
    inferred_schema_obj = infer_schema_sync(
        sample=sample,
        provider=provider,
        chunk_size=config.chunking.columns_per_chunk,
        use_smart_chunking=True,
    )

    # Convert to dict for comparison
    inferred_schema = {
        col.name: col.pg_type
        for col in inferred_schema_obj.columns
    }
    print(f"   Inferred {len(inferred_schema)} columns")
    print()

    # Step 3: Compare schemas
    print("📊 Step 3: Comparing schemas...")
    matches, mismatches, missing = generate_comparison_report(
        inferred_schema=inferred_schema,
        reference_schema=reference_schema,
        output_file=output_file
    )
    print()

    # Step 4: Exit with appropriate code
    if mismatches > 0 or missing > 0:
        print("❌ VALIDATION FAILED: There are mismatches or missing columns")
        print(f"   See detailed report in: {output_file}")
        sys.exit(1)
    else:
        print("✅ VALIDATION PASSED: All columns match!")
        print(f"   See detailed report in: {output_file}")
        sys.exit(0)


if __name__ == "__main__":
    main()

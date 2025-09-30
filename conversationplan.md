CONVERSATION PLAN: csv2pg-ai-schema-infer Optimization
========================================================
Date: September 30, 2025
Project: /root/Projects/csv2pg-ai-schema-infer
Purpose: Fix AI-generated pgloader schema issues and optimize for large CSV imports

=============================================================================
EXECUTIVE SUMMARY
=============================================================================

This project uses AI to generate pgloader configuration files from CSV samples.
The current AI-generated output has CRITICAL bugs that produce invalid SQL and
poor performance settings.

USER CONTEXT:
- 32 CPU cores, 32GB RAM server
- Target dataset: organizations.csv (7.7GB, 5.1M rows, 156 columns)
- Current estimated import time: 45-60 minutes
- Goal: 15-25 minutes with reliable, correct schema

CRITICAL ISSUES FOUND:
1. ❌ DUPLICATE PRIMARY KEYS (invalid SQL - causes failures)
2. ❌ Unescaped dots in column names (identifier.uuid instead of identifier_uuid)
3. ❌ Wrong array handling (CSV strings treated as PostgreSQL arrays)
4. ❌ PRIMARY KEY created during load (slow) vs AFTER LOAD (fast)
5. ❌ BIGINT for currency (loses decimals) instead of NUMERIC
6. ❌ Missing performance parameters (workers, concurrency, batch size)
7. ❌ Overly aggressive NOT NULL constraints

=============================================================================
BACKGROUND: HOW THE SYSTEM WORKS
=============================================================================

PROJECT STRUCTURE:
/root/Projects/csv2pg-ai-schema-infer/
├── src/csv2pg_ai_schema_infer/
│   ├── generator.py          # Main AI schema generator
│   ├── inference.py          # Type inference from CSV samples
│   ├── config.py             # Configuration settings
│   ├── types.py              # Data type definitions
│   └── templates/
│       └── pgloader.jinja2   # Template for pgloader .load files
└── tests/
    └── examples/
        ├── Compare_Example.load      # ✅ Hand-crafted (CORRECT)
        └── organizations_output.load # ❌ AI-generated (BROKEN)

WORKFLOW:
1. User provides CSV file
2. System samples first N rows (default: 1000)
3. AI (via inference.py) analyzes sample and infers:
   - Column types (text, integer, numeric, uuid, timestamp, etc.)
   - NULL constraints
   - Primary key candidates
   - Array vs scalar types
4. generator.py uses pgloader.jinja2 template to create .load file
5. User runs pgloader with the .load file to import into PostgreSQL

THE PROBLEM:
The AI is making incorrect inferences that produce invalid/inefficient SQL.

=============================================================================
DETAILED ISSUE ANALYSIS
=============================================================================

ISSUE #1: DUPLICATE PRIMARY KEYS (CRITICAL)
--------------------------------------------
CURRENT BEHAVIOR (AI-generated):
  Line 21:  identifier_uuid UUID NOT NULL PRIMARY KEY,
  Line 38:  identifier_image_id TEXT NOT NULL PRIMARY KEY,

PROBLEM:
  PostgreSQL allows ONLY ONE PRIMARY KEY per table. This is INVALID SQL.
  The pgloader file will FAIL to execute.

ROOT CAUSE:
  AI is marking multiple columns as PRIMARY KEY candidates without
  enforcing the constraint that only ONE can be chosen.

EXPECTED BEHAVIOR (from Compare_Example.load):
  CREATE TABLE:
    identifier_uuid uuid,   -- No PK during CREATE
  
  AFTER LOAD:
    ALTER TABLE public.organizations 
    ADD PRIMARY KEY (identifier_uuid);  -- PK added AFTER data load

WHY AFTER LOAD:
  Adding PK during CREATE forces index building per-row (very slow).
  Adding PK after data load allows bulk index creation (3-5x faster).


ISSUE #2: COLUMN NAME NORMALIZATION (CRITICAL)
-----------------------------------------------
CURRENT BEHAVIOR (AI-generated):
  identifier.uuid, identifier.entity_def_id, funding_total.value

PROBLEM:
  Dots in PostgreSQL column names require quoting: "identifier.uuid"
  This causes issues with ORMs, queries, and is considered bad practice.

EXPECTED BEHAVIOR (from Compare_Example.load):
  identifier_uuid, identifier_entity_def_id, funding_total_value

SOLUTION:
  Replace ALL dots with underscores during column name sanitization.
  Pattern: s/\./_/g for all column names


ISSUE #3: ARRAY TYPE HANDLING (CRITICAL)
-----------------------------------------
CURRENT BEHAVIOR (AI-generated):
  CREATE TABLE:
    categories_uuid UUID[],
    aliases TEXT[],

PROBLEM:
  CSV has comma-separated strings: "uuid1,uuid2,uuid3"
  These are TEXT fields in CSV, NOT PostgreSQL arrays.
  Direct typing as UUID[] causes import failures.

EXPECTED BEHAVIOR (from Compare_Example.load):
  CREATE TABLE:
    categories_uuid text,  -- Keep as text during load
    aliases text,
  
  CAST:
    categories_uuid to text using null if blanks,
    aliases to text using null if blanks

  If conversion needed, use AFTER LOAD:
    ALTER TABLE ... ADD COLUMN categories_uuid_array UUID[];
    UPDATE ... SET categories_uuid_array = string_to_array(categories_uuid, ',')::UUID[];

SOLUTION:
  Detect comma-separated values but keep as TEXT in CREATE TABLE.
  Add CAST rules for string_to_array if needed AFTER data loads.


ISSUE #4: PRIMARY KEY TIMING (CRITICAL PERFORMANCE)
----------------------------------------------------
CURRENT BEHAVIOR (AI-generated):
  CREATE TABLE:
    identifier_uuid UUID NOT NULL PRIMARY KEY,  -- During table creation

PROBLEM:
  For 5.1M rows, this builds the index row-by-row (extremely slow).
  Estimated penalty: 30-40 minutes extra time.

EXPECTED BEHAVIOR (from Compare_Example.load):
  CREATE TABLE:
    identifier_uuid uuid,  -- No constraints during creation
  
  AFTER LOAD DO
  $$
    ALTER TABLE public.organizations ADD PRIMARY KEY (identifier_uuid);
  $$;

PERFORMANCE IMPACT:
  - During CREATE: ~60 minutes
  - AFTER LOAD: ~20 minutes
  Speedup: 3x faster


ISSUE #5: NUMERIC TYPE PRECISION (CRITICAL DATA INTEGRITY)
-----------------------------------------------------------
CURRENT BEHAVIOR (AI-generated):
  equity_funding_total_value_usd BIGINT

PROBLEM:
  BIGINT is for whole numbers only: 1234567890
  Currency values have decimals: 1234567.89
  Using BIGINT truncates/loses decimal precision.

EXPECTED BEHAVIOR (from Compare_Example.load):
  equity_funding_total_value_usd numeric

NUMERIC vs BIGINT:
  NUMERIC: Arbitrary precision, handles decimals
  BIGINT: 64-bit integer, no decimals
  
  For currency, financial data, percentages → NUMERIC
  For counts, IDs, row numbers → BIGINT


ISSUE #6: MISSING PERFORMANCE PARAMETERS (MAJOR)
-------------------------------------------------
CURRENT BEHAVIOR (AI-generated):
  WITH
      truncate,
      skip header = 1,
      fields optionally enclosed by '"',
      fields escaped by double-quote,
      fields terminated by ','
  
  SET
      work_mem to '256MB',
      maintenance_work_mem to '512MB'

PROBLEM:
  Missing critical pgloader performance parameters:
  - workers: Number of threads for parallel CSV reading
  - concurrency: Number of parallel PostgreSQL connections
  - batch size: Size of batches sent to PostgreSQL
  - prefetch rows: Row buffer size

EXPECTED BEHAVIOR (for 32-core/32GB server):
  WITH
      workers = 16,                  -- Use 16 threads for CSV parsing
      concurrency = 8,               -- 8 parallel DB connections
      batch size = 50MB,             -- 50MB batches
      prefetch rows = 25000,         -- 25k row buffer
      truncate,
      skip header = 1,
      fields optionally enclosed by '"',
      fields escaped by double-quote,
      fields terminated by ','
  
  SET
      work_mem to '512MB',           -- Increased from 256MB
      maintenance_work_mem to '2GB'  -- Increased from 512MB

PERFORMANCE IMPACT:
  - Without parameters: Single-threaded, slow
  - With parameters: Parallel processing, 3x faster

RATIONALE FOR VALUES (32-core/32GB server):
  workers=16:
    - Uses 50% of CPU cores
    - Parallel CSV parsing and data transformation
    - Sweet spot: cores/2 to cores*0.75
  
  concurrency=8:
    - Parallel PostgreSQL connections
    - Sweet spot: workers/2 to workers*0.75
    - Too high overwhelms DB, too low underutilizes CPU
  
  batch size=50MB:
    - Larger batches reduce network overhead
    - For 7.7GB file: ~154 batches
    - Sweet spot: 25-100MB for multi-GB files
  
  prefetch rows=25000:
    - Buffer between CSV reader and DB writer
    - For 156 columns: ~25k rows ≈ 20-30MB buffer
    - Prevents pipeline stalls
  
  work_mem=512MB:
    - Per-operation memory for sorting/hashing
    - 8 concurrent ops * 512MB = 4GB (safe for 32GB RAM)
  
  maintenance_work_mem=2GB:
    - For index creation in AFTER LOAD
    - Critical for fast PRIMARY KEY creation on 5M rows


ISSUE #7: OVERLY AGGRESSIVE NOT NULL (MAJOR)
---------------------------------------------
CURRENT BEHAVIOR (AI-generated):
  description TEXT NOT NULL,
  rank_delta_d30 REAL NOT NULL,

PROBLEM:
  AI marks columns as NOT NULL based on small sample (1000 rows).
  In full dataset, these columns may have NULLs → import fails.

EXPECTED BEHAVIOR (from Compare_Example.load):
  description text,  -- Allow NULL unless certain
  rank_delta_d30 numeric using null if blanks,

SOLUTION:
  Only mark as NOT NULL if:
  - Column is PRIMARY KEY, or
  - 99.9%+ non-null in large sample (10k+ rows), or
  - Explicitly known to be required (e.g., username, email)

=============================================================================
STEP-BY-STEP IMPLEMENTATION PLAN
=============================================================================

PHASE 1: FIX CORE SCHEMA GENERATION ISSUES
-------------------------------------------

STEP 1: Update Column Name Sanitization
FILE: src/csv2pg_ai_schema_infer/generator.py or inference.py

CURRENT:
  Column names likely not sanitized, or only partially sanitized.

REQUIRED CHANGES:
  1. Find column name processing function
  2. Add regex replacement: column_name.replace('.', '_')
  3. Also handle other special chars: spaces, hyphens, etc.
  4. Pattern: 
     - Lowercase all names (PostgreSQL convention)
     - Replace [^a-z0-9_] with underscore
     - Ensure first char is letter or underscore
     - Handle reserved keywords (add prefix like "col_")

EXAMPLE CODE:
  def sanitize_column_name(name: str) -> str:
      """Sanitize column name for PostgreSQL."""
      # Replace dots and special chars with underscores
      name = re.sub(r'[^a-z0-9_]', '_', name.lower())
      # Ensure starts with letter or underscore
      if name[0].isdigit():
          name = f'col_{name}'
      # Handle reserved keywords
      if name in POSTGRES_RESERVED_KEYWORDS:
          name = f'{name}_'
      return name

VALIDATION:
  Test: "identifier.uuid" → "identifier_uuid"
  Test: "funding_total.value" → "funding_total_value"
  Test: "Rank Delta (d30)" → "rank_delta_d30"


STEP 2: Fix PRIMARY KEY Logic
FILE: src/csv2pg_ai_schema_infer/generator.py
FILE: src/csv2pg_ai_schema_infer/templates/pgloader.jinja2

CURRENT:
  Multiple columns marked with PRIMARY KEY in CREATE TABLE.

REQUIRED CHANGES:

A) In generator.py or inference.py:
   1. Identify PRIMARY KEY candidates (uuid, id, etc.)
   2. Rank candidates by priority:
      - Columns named 'id' or '*_id' with unique values
      - UUID columns
      - Composite keys (if necessary)
   3. Select ONLY ONE primary key
   4. Store in schema metadata: primary_key_column = "identifier_uuid"
   5. Remove PRIMARY KEY from column definition

B) In pgloader.jinja2 template:
   1. Remove PRIMARY KEY from CREATE TABLE section
   2. Add to AFTER LOAD section:
      
      AFTER LOAD DO
      $$
        -- Add primary key
        ALTER TABLE {{ schema }}.{{ table_name }} 
        ADD PRIMARY KEY ({{ primary_key_column }});
        
        -- Analyze table for query optimization
        ANALYZE {{ schema }}.{{ table_name }};
      $$;

VALIDATION:
  - Only ONE ALTER TABLE ... ADD PRIMARY KEY in output
  - No PRIMARY KEY in CREATE TABLE column definitions
  - PK added after data load completes


STEP 3: Fix Array Type Detection
FILE: src/csv2pg_ai_schema_infer/inference.py

CURRENT:
  AI detects comma-separated values and infers PostgreSQL array types.

REQUIRED CHANGES:
  1. Find array detection logic
  2. Keep detected info (is_comma_separated) but don't use array type in CREATE
  3. Use TEXT type in CREATE TABLE
  4. Add metadata flag: needs_array_conversion = True
  5. In CAST section, use:
     column_name to text using null if blanks
  6. (Optional) In AFTER LOAD, add array conversion if needed

LOGIC:
  def infer_type(column_values):
      has_commas = any(',' in str(v) for v in column_values)
      
      if has_commas:
          # Looks like comma-separated values
          # But keep as TEXT for CSV import
          return {
              'sql_type': 'text',
              'needs_array_conversion': True,
              'array_element_type': infer_element_type(column_values)
          }
      else:
          return infer_scalar_type(column_values)

TEMPLATE CHANGES (pgloader.jinja2):
  CAST section:
    {% for col in columns %}
      {% if col.needs_array_conversion %}
        {{ col.name }} to text using null if blanks,
      {% endif %}
    {% endfor %}

VALIDATION:
  - categories_uuid: TEXT in CREATE, not UUID[]
  - aliases: TEXT in CREATE, not TEXT[]
  - CAST: "to text using null if blanks"


STEP 4: Fix Numeric Type Selection
FILE: src/csv2pg_ai_schema_infer/inference.py

CURRENT:
  AI uses BIGINT for large numbers, even with decimals.

REQUIRED CHANGES:
  1. Find numeric type inference logic
  2. Check for decimal points in sample values
  3. Use decision tree:
     
     IF has_decimal_point:
         IF max_value < 1e6 AND decimal_places <= 2:
             type = 'NUMERIC(12, 2)'  # For currency
         ELSE:
             type = 'NUMERIC'  # For general decimals
     ELSE IF max_value < 2^31:
         type = 'INTEGER'
     ELSE IF max_value < 2^63:
         type = 'BIGINT'
     ELSE:
         type = 'NUMERIC'

  4. Special handling for currency columns:
     - Column name contains: 'price', 'value', 'usd', 'amount', 'total'
     - Use NUMERIC instead of BIGINT

VALIDATION:
  - equity_funding_total_value_usd: NUMERIC (not BIGINT)
  - rank_delta_d30: NUMERIC (has decimals)
  - employee_count: INTEGER or BIGINT (whole numbers)


STEP 5: Fix NOT NULL Inference
FILE: src/csv2pg_ai_schema_infer/inference.py

CURRENT:
  AI applies NOT NULL to columns with no nulls in sample.

REQUIRED CHANGES:
  1. Calculate null_ratio = null_count / total_rows
  2. Apply NOT NULL only if:
     - null_ratio == 0 AND sample_size >= 10000, OR
     - Column is primary_key, OR
     - Column is explicitly marked as required
  3. Default to allowing NULL (safer for imports)

LOGIC:
  def should_be_not_null(column_stats, is_primary_key):
      if is_primary_key:
          return True
      
      null_ratio = column_stats['null_count'] / column_stats['total_rows']
      sample_size = column_stats['total_rows']
      
      # Conservative: require large sample with zero nulls
      if null_ratio == 0 and sample_size >= 10000:
          return True
      
      return False

VALIDATION:
  - Only PRIMARY KEY has NOT NULL in CREATE TABLE
  - Other columns allow NULL
  - CAST section handles nulls: "using null if blanks"


STEP 6: Fix CAST Rules Syntax
FILE: src/csv2pg_ai_schema_infer/templates/pgloader.jinja2

CURRENT (BROKEN):
  categories_uuid: Split the input string by ',' into a text array.

EXPECTED:
  categories_uuid to text using null if blanks,

REQUIRED CHANGES:
  1. Find CAST section in template
  2. Use proper pgloader syntax:
     
     CAST
       column_name to postgresql_type [using transformation]
     
  3. Common patterns:
     - Integer with blanks: col to integer using null if blanks
     - Numeric with blanks: col to numeric using null if blanks
     - Text: col to text using null if blanks
     - UUID: col to uuid using null if blanks
     - Timestamp: col to timestamptz using null if blanks

  4. Remove any invalid "Split the input string..." syntax

TEMPLATE STRUCTURE:
  CAST
    {% for col in columns %}
      {{ col.name }} to {{ col.cast_type }} {% if col.allow_null %}using null if blanks{% endif %},
    {% endfor %}

VALIDATION:
  - No plain English in CAST section
  - All CAST rules end with comma except last
  - Valid pgloader syntax


---

PHASE 2: ADD PERFORMANCE OPTIMIZATIONS
---------------------------------------

STEP 7: Add pgloader Performance Parameters
FILE: src/csv2pg_ai_schema_infer/templates/pgloader.jinja2
FILE: src/csv2pg_ai_schema_infer/config.py

REQUIRED CHANGES:

A) Add to config.py:
   import multiprocessing
   
   class PgloaderConfig:
       # Auto-detect CPU cores
       cpu_cores = multiprocessing.cpu_count()
       
       # Performance parameters (with auto-scaling)
       workers = max(8, cpu_cores // 2)  # 50% of cores
       concurrency = max(4, workers // 2)
       batch_size = '50MB'
       prefetch_rows = 25000
       work_mem = '512MB'
       maintenance_work_mem = '2GB'
       
       @classmethod
       def for_file_size(cls, file_size_gb):
           """Scale parameters based on file size."""
           if file_size_gb < 1:
               return cls(workers=4, concurrency=2, batch_size='25MB')
           elif file_size_gb < 5:
               return cls(workers=8, concurrency=4, batch_size='50MB')
           else:  # Large files (5+ GB)
               return cls(workers=16, concurrency=8, batch_size='100MB')

B) Update pgloader.jinja2 template:
   
   WITH
       workers = {{ config.workers }},
       concurrency = {{ config.concurrency }},
       batch size = {{ config.batch_size }},
       prefetch rows = {{ config.prefetch_rows }},
       truncate,
       skip header = 1,
       fields optionally enclosed by '"',
       fields escaped by double-quote,
       fields terminated by ','
   
   SET
       work_mem to '{{ config.work_mem }}',
       maintenance_work_mem to '{{ config.maintenance_work_mem }}'

VALIDATION:
  - Workers = 8-16 for 32-core system
  - Concurrency = 4-8
  - Batch size = 50MB for 7.7GB file
  - Memory settings scaled appropriately


STEP 8: Optimize Memory Settings
FILE: src/csv2pg_ai_schema_infer/config.py

CURRENT:
  work_mem = 256MB
  maintenance_work_mem = 512MB

REQUIRED:
  Calculate based on available system RAM.
  
  FORMULA:
    total_ram = psutil.virtual_memory().total
    work_mem = min(512MB, total_ram * 0.05 / concurrency)
    maintenance_work_mem = min(2GB, total_ram * 0.1)
  
  FOR 32GB RAM:
    work_mem = 512MB (safe for 8 concurrent connections)
    maintenance_work_mem = 2GB (for index building)

IMPLEMENTATION:
  import psutil
  
  def calculate_memory_settings(concurrency):
      total_ram_gb = psutil.virtual_memory().total / (1024**3)
      
      # work_mem: per-operation memory
      # Safe formula: total_ram * 0.15 / concurrency
      work_mem_mb = min(512, int(total_ram_gb * 150 / concurrency))
      
      # maintenance_work_mem: for index/vacuum operations
      maint_mem_mb = min(2048, int(total_ram_gb * 100))
      
      return {
          'work_mem': f'{work_mem_mb}MB',
          'maintenance_work_mem': f'{maint_mem_mb}MB'
      }


STEP 9: Add Complete AFTER LOAD Section
FILE: src/csv2pg_ai_schema_infer/templates/pgloader.jinja2

CURRENT:
  Missing or incomplete AFTER LOAD section.

REQUIRED STRUCTURE:
  AFTER LOAD DO
  $$
    -- Add primary key (fast bulk index creation)
    ALTER TABLE {{ schema }}.{{ table_name }} 
    ADD PRIMARY KEY ({{ primary_key_column }});
    
    {% if unique_columns %}
    -- Add unique constraints
    {% for col in unique_columns %}
    CREATE UNIQUE INDEX idx_{{ table_name }}_{{ col }}_unique 
    ON {{ schema }}.{{ table_name }} ({{ col }});
    {% endfor %}
    {% endif %}
    
    {% if foreign_keys %}
    -- Add indexes for foreign key columns (improves JOIN performance)
    {% for fk in foreign_keys %}
    CREATE INDEX idx_{{ table_name }}_{{ fk.column }} 
    ON {{ schema }}.{{ table_name }} ({{ fk.column }});
    {% endfor %}
    {% endif %}
    
    -- Update table statistics for query planner
    ANALYZE {{ schema }}.{{ table_name }};
  $$;

BENEFITS:
  - PRIMARY KEY added after load: 3-5x faster
  - Indexes created on bulk data: 2-3x faster
  - ANALYZE provides accurate stats for query optimization


---

PHASE 3: CONFIGURATION SYSTEM
------------------------------

STEP 10: Create Comprehensive Config System
FILE: src/csv2pg_ai_schema_infer/config.py

REQUIRED ADDITIONS:

import multiprocessing
import psutil
from dataclasses import dataclass
from typing import Optional

@dataclass
class PerformanceConfig:
    """Performance settings for pgloader."""
    
    # CPU settings
    workers: int
    concurrency: int
    
    # Memory settings
    batch_size: str
    prefetch_rows: int
    work_mem: str
    maintenance_work_mem: str
    
    @classmethod
    def auto_detect(cls, file_size_gb: Optional[float] = None):
        """Auto-detect optimal settings based on system resources."""
        cpu_cores = multiprocessing.cpu_count()
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        
        # Scale workers based on CPU cores
        if cpu_cores >= 32:
            workers = 16
        elif cpu_cores >= 16:
            workers = 8
        else:
            workers = max(4, cpu_cores // 2)
        
        concurrency = max(4, workers // 2)
        
        # Scale batch size based on file size
        if file_size_gb and file_size_gb > 5:
            batch_size = '100MB'
            prefetch_rows = 50000
        else:
            batch_size = '50MB'
            prefetch_rows = 25000
        
        # Calculate memory settings
        work_mem_mb = min(512, int(total_ram_gb * 150 / concurrency))
        maint_mem_gb = min(2, int(total_ram_gb * 0.1))
        
        return cls(
            workers=workers,
            concurrency=concurrency,
            batch_size=batch_size,
            prefetch_rows=prefetch_rows,
            work_mem=f'{work_mem_mb}MB',
            maintenance_work_mem=f'{maint_mem_gb}GB'
        )


STEP 11: Add Validation Layer
FILE: src/csv2pg_ai_schema_infer/validator.py (NEW FILE)

PURPOSE:
  Validate AI-generated schema before writing to file.
  Catch errors early before pgloader execution.

REQUIRED CHECKS:

class SchemaValidator:
    """Validate generated pgloader schema."""
    
    def validate(self, schema_dict):
        """Run all validation checks."""
        errors = []
        warnings = []
        
        # Check 1: Only one primary key
        pk_count = sum(1 for col in schema_dict['columns'] 
                      if col.get('is_primary_key'))
        if pk_count > 1:
            errors.append(f"Multiple PRIMARY KEYs detected: {pk_count}")
        
        # Check 2: Valid column names (no dots, special chars)
        for col in schema_dict['columns']:
            if '.' in col['name']:
                errors.append(f"Invalid column name: {col['name']} (contains dot)")
        
        # Check 3: No array types in CREATE TABLE for CSV import
        for col in schema_dict['columns']:
            if '[]' in col['sql_type']:
                warnings.append(f"Array type {col['sql_type']} for {col['name']} "
                              "may fail CSV import")
        
        # Check 4: Valid CAST syntax
        for cast_rule in schema_dict.get('cast_rules', []):
            if 'Split the input' in cast_rule:
                errors.append(f"Invalid CAST syntax: {cast_rule}")
        
        # Check 5: Currency columns use NUMERIC not BIGINT
        for col in schema_dict['columns']:
            if any(x in col['name'] for x in ['usd', 'price', 'value', 'amount']):
                if col['sql_type'].upper() == 'BIGINT':
                    warnings.append(f"Column {col['name']} uses BIGINT, "
                                  "consider NUMERIC for precision")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

INTEGRATION:
  In generator.py, before writing output:
    
    validator = SchemaValidator()
    result = validator.validate(schema_dict)
    
    if not result['valid']:
        raise SchemaValidationError(result['errors'])
    
    if result['warnings']:
        logger.warning("Schema warnings:", result['warnings'])


---

PHASE 4: TESTING & VALIDATION
------------------------------

STEP 12: Create Schema Comparison Tool
FILE: tools/compare_schemas.py (NEW FILE)

PURPOSE:
  Compare AI-generated schema with hand-crafted reference.
  Identify differences and issues.

IMPLEMENTATION:

import difflib
from pathlib import Path

def compare_schemas(ai_generated_path, manual_path, output_path=None):
    """Compare two pgloader .load files and report differences."""
    
    with open(ai_generated_path) as f:
        ai_lines = f.readlines()
    
    with open(manual_path) as f:
        manual_lines = f.readlines()
    
    # Generate unified diff
    diff = difflib.unified_diff(
        manual_lines, 
        ai_lines,
        fromfile='Manual (Reference)',
        tofile='AI Generated',
        lineterm=''
    )
    
    diff_lines = list(diff)
    
    # Analyze differences
    issues = {
        'duplicate_primary_keys': [],
        'column_name_issues': [],
        'array_type_issues': [],
        'numeric_type_issues': [],
        'missing_performance_params': []
    }
    
    # Check for issues
    for i, line in enumerate(ai_lines):
        # Check for duplicate PKs
        if 'PRIMARY KEY' in line and 'CREATE TABLE' in ''.join(ai_lines[:i]):
            issues['duplicate_primary_keys'].append((i, line))
        
        # Check for dots in column names
        if '.' in line and 'CREATE TABLE' in ''.join(ai_lines[:i]):
            issues['column_name_issues'].append((i, line))
        
        # Check for array types
        if '[]' in line and ('UUID[]' in line or 'TEXT[]' in line):
            issues['array_type_issues'].append((i, line))
        
        # Check for BIGINT on currency columns
        if 'BIGINT' in line and any(x in line.lower() 
                                    for x in ['usd', 'value', 'price']):
            issues['numeric_type_issues'].append((i, line))
    
    # Check for missing performance params
    ai_content = ''.join(ai_lines)
    if 'workers' not in ai_content:
        issues['missing_performance_params'].append('workers')
    if 'concurrency' not in ai_content:
        issues['missing_performance_params'].append('concurrency')
    
    # Generate report
    report = generate_comparison_report(diff_lines, issues)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    
    return report, issues

USAGE:
  python tools/compare_schemas.py \
      --ai tests/examples/organizations_output.load \
      --manual tests/examples/Compare_Example.load \
      --output schema_comparison_report.txt


STEP 13: Add Dry-Run Validation
FILE: src/csv2pg_ai_schema_infer/validator.py

PURPOSE:
  Test SQL syntax without executing against database.
  Catch syntax errors before pgloader run.

IMPLEMENTATION:

import sqlparse
from sqlparse import sql, tokens

def validate_sql_syntax(load_file_path):
    """Validate SQL syntax in pgloader .load file."""
    
    with open(load_file_path) as f:
        content = f.read()
    
    # Extract SQL sections (CREATE TABLE, AFTER LOAD)
    create_table = extract_create_table_sql(content)
    after_load = extract_after_load_sql(content)
    
    errors = []
    
    # Parse CREATE TABLE
    try:
        parsed = sqlparse.parse(create_table)
        if not parsed:
            errors.append("Failed to parse CREATE TABLE statement")
    except Exception as e:
        errors.append(f"CREATE TABLE syntax error: {e}")
    
    # Parse AFTER LOAD
    try:
        parsed = sqlparse.parse(after_load)
        if not parsed:
            errors.append("Failed to parse AFTER LOAD statement")
    except Exception as e:
        errors.append(f"AFTER LOAD syntax error: {e}")
    
    # Check for common issues
    if 'PRIMARY KEY' in create_table:
        pk_count = create_table.count('PRIMARY KEY')
        if pk_count > 1:
            errors.append(f"Multiple PRIMARY KEY constraints: {pk_count}")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


STEP 14: Test with organizations.csv
FILE: tests/test_organizations_import.py (NEW FILE)

PURPOSE:
  End-to-end test with actual 7.7GB file.
  Measure performance improvements.

TEST PLAN:

1. Generate schema with OLD code:
   - Time schema generation
   - Run validator
   - Attempt pgloader import
   - Measure import time
   - Verify data integrity

2. Generate schema with NEW code:
   - Time schema generation
   - Run validator (should pass)
   - Run pgloader import
   - Measure import time
   - Verify data integrity
   - Compare with old results

3. Metrics to collect:
   - Schema generation time
   - Validation pass/fail
   - pgloader import time
   - Rows imported
   - Errors encountered
   - Index creation time

EXPECTED RESULTS:
   OLD: 45-60 min import, validation errors, possible failures
   NEW: 15-25 min import, clean validation, successful import

=============================================================================
IMPLEMENTATION CHECKLIST
=============================================================================

Core Fixes (CRITICAL - Must Do First):
□ Fix column name sanitization (dots → underscores)
□ Fix PRIMARY KEY logic (only one, in AFTER LOAD)
□ Fix array type detection (CSV → TEXT, not array types)
□ Fix numeric type selection (NUMERIC for decimals/currency)
□ Fix NOT NULL inference (more conservative)
□ Fix CAST syntax (remove plain English, use pgloader syntax)

Performance Optimizations (HIGH PRIORITY):
□ Add workers parameter to template
□ Add concurrency parameter to template
□ Add batch size parameter to template
□ Add prefetch rows parameter to template
□ Increase work_mem to 512MB
□ Increase maintenance_work_mem to 2GB
□ Add complete AFTER LOAD section with PK + indexes + ANALYZE

Configuration System (MEDIUM PRIORITY):
□ Create PerformanceConfig class with auto-detection
□ Add CPU core detection
□ Add RAM detection
□ Add file size-based scaling
□ Integrate config into generator

Validation System (MEDIUM PRIORITY):
□ Create SchemaValidator class
□ Add duplicate PK check
□ Add column name validation
□ Add array type validation
□ Add CAST syntax validation
□ Add numeric type validation
□ Integrate into generator pipeline

Testing & Tools (NICE TO HAVE):
□ Create schema comparison tool
□ Add SQL syntax dry-run validator
□ Create end-to-end test with organizations.csv
□ Document performance metrics before/after

=============================================================================
FILES TO MODIFY (In Order of Priority)
=============================================================================

1. src/csv2pg_ai_schema_infer/inference.py
   - Fix type inference logic (numeric, arrays, NOT NULL)
   - Add column name sanitization
   - Add PRIMARY KEY candidate selection

2. src/csv2pg_ai_schema_infer/templates/pgloader.jinja2
   - Add performance parameters (workers, concurrency, etc.)
   - Remove PRIMARY KEY from CREATE TABLE
   - Add AFTER LOAD section with PK + indexes
   - Fix CAST section syntax

3. src/csv2pg_ai_schema_infer/generator.py
   - Integrate new config system
   - Add validation before output
   - Ensure only one PK selected

4. src/csv2pg_ai_schema_infer/config.py
   - Add PerformanceConfig class
   - Add auto-detection logic
   - Add scaling formulas

5. src/csv2pg_ai_schema_infer/validator.py (NEW)
   - Create SchemaValidator class
   - Add all validation checks

6. tools/compare_schemas.py (NEW)
   - Create comparison tool
   - Generate reports

7. tests/test_organizations_import.py (NEW)
   - Add end-to-end test
   - Measure performance

=============================================================================
EXPECTED OUTCOMES
=============================================================================

BEFORE (Current AI-Generated):
❌ Invalid SQL (duplicate PRIMARY KEYs)
❌ Import failures (column name issues, array types)
❌ Slow performance (45-60 minutes for 5M rows)
❌ Data precision loss (BIGINT for currency)
❌ No performance tuning parameters
❌ Index creation during load (very slow)

AFTER (Optimized):
✅ Valid SQL (single PRIMARY KEY in AFTER LOAD)
✅ Successful imports (proper column names, TEXT types)
✅ Fast performance (15-25 minutes for 5M rows, 3x speedup)
✅ Data integrity (NUMERIC for decimals/currency)
✅ Optimal performance parameters (workers, concurrency, batch size)
✅ Index creation after load (bulk operation, 3-5x faster)

PERFORMANCE IMPROVEMENTS:
- Import time: 45-60 min → 15-25 min (3x faster)
- Schema generation: More reliable, fewer errors
- Resource utilization: 50% CPU → 90%+ CPU (better parallelization)
- Memory efficiency: Proper work_mem/maintenance_work_mem sizing

=============================================================================
TECHNICAL REFERENCE
=============================================================================

PGLOADER SYNTAX REFERENCE:

1. WITH section (CSV parsing and performance):
   WITH
       workers = N,              -- Number of parallel worker threads
       concurrency = N,          -- Number of parallel DB connections
       batch size = 'NNMB',      -- Batch size for commits
       prefetch rows = N,        -- Row buffer size
       truncate,                 -- Truncate table before load
       skip header = 1,          -- Skip first row (header)
       fields optionally enclosed by '"',
       fields escaped by double-quote,
       fields terminated by ','

2. SET section (PostgreSQL settings):
   SET
       work_mem to 'NNMB',              -- Per-operation memory
       maintenance_work_mem to 'NNGB'   -- For index/vacuum ops

3. CAST section (type transformations):
   CAST
       column1 to integer using null if blanks,
       column2 to numeric using null if blanks,
       column3 to uuid using null if blanks,
       column4 to text

4. AFTER LOAD section (post-import operations):
   AFTER LOAD DO
   $$
       ALTER TABLE schema.table ADD PRIMARY KEY (column);
       CREATE INDEX idx_name ON schema.table (column);
       ANALYZE schema.table;
   $$;

POSTGRESQL TYPE REFERENCE:

- INTEGER: 4-byte int, range -2^31 to 2^31-1
- BIGINT: 8-byte int, range -2^63 to 2^63-1
- NUMERIC / NUMERIC(p,s): Arbitrary precision decimal
- REAL: 4-byte float, 6 decimal digits precision
- DOUBLE PRECISION: 8-byte float, 15 decimal digits precision
- TEXT: Variable-length text
- VARCHAR(n): Variable-length text with limit
- UUID: 128-bit universally unique identifier
- TIMESTAMP / TIMESTAMPTZ: Date and time (with/without timezone)
- BOOLEAN: true/false
- ARRAY types: type[] (e.g., INTEGER[], TEXT[], UUID[])

WHEN TO USE EACH TYPE:
- Currency: NUMERIC(12, 2) or NUMERIC
- Counts/IDs: INTEGER or BIGINT
- Percentages: NUMERIC or REAL
- Names/descriptions: TEXT
- Email/URL: TEXT or VARCHAR(255)
- Timestamps: TIMESTAMPTZ (with timezone)
- Flags: BOOLEAN
- UUID identifiers: UUID
- Comma-separated in CSV: TEXT (parse in app or use string_to_array)

=============================================================================
TROUBLESHOOTING GUIDE FOR NEXT AI AGENT
=============================================================================

COMMON ERRORS AND SOLUTIONS:

1. ERROR: duplicate key value violates unique constraint "pg_type_typname_nsp_index"
   CAUSE: Trying to create duplicate PRIMARY KEY
   FIX: Ensure only ONE PRIMARY KEY in entire schema

2. ERROR: column "identifier.uuid" does not exist
   CAUSE: Column name has unescaped dot
   FIX: Replace dots with underscores in column names

3. ERROR: malformed array literal: "value1,value2"
   CAUSE: CSV comma-separated string treated as PostgreSQL array
   FIX: Use TEXT type in CREATE TABLE, parse in application

4. ERROR: numeric field overflow
   CAUSE: Using BIGINT for decimal values
   FIX: Use NUMERIC type for currency and decimal data

5. WARNING: pgloader taking 60+ minutes for 5M rows
   CAUSE: Missing performance parameters or index during load
   FIX: Add workers/concurrency, move PK to AFTER LOAD

6. ERROR: could not extend file "base/...": No space left on device
   CAUSE: work_mem or maintenance_work_mem too high
   FIX: Reduce to safe values based on available RAM

=============================================================================
NEXT STEPS FOR AI AGENT
=============================================================================

START HERE:
1. Read this entire plan document
2. Read the comparison between:
   - /root/Projects/csv2pg-ai-schema-infer/tests/examples/Compare_Example.load
   - /root/Projects/csv2pg-ai-schema-infer/tests/examples/organizations_output.load
3. Examine current codebase structure
4. Begin with Phase 1, Step 1 (column name sanitization)
5. Work through checklist sequentially
6. Test after each major change
7. Create schema comparison report at end

PRIORITIES:
1. Fix CRITICAL bugs first (duplicate PK, column names, arrays)
2. Add performance parameters second
3. Add validation system third
4. Create testing tools last

VALIDATION:
After implementation, generate new schema for organizations.csv and verify:
- No duplicate PRIMARY KEYs
- All column names use underscores, no dots
- No array types in CREATE TABLE
- NUMERIC used for currency columns
- Performance parameters present (workers, concurrency, etc.)
- AFTER LOAD section exists with PK + indexes
- Validator catches all known issues

COMMUNICATION:
- Document all changes made
- Note any deviations from plan
- Report final performance metrics
- Create before/after comparison

=============================================================================
END OF PLAN
=============================================================================

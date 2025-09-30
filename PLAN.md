# PLAN.md

## Project: CSV2PG - Intelligent CSV to PostgreSQL Import Pipeline

### Executive Summary

A modular Python application that automates the process of importing large CSV files into PostgreSQL databases via pgloader. The system uses AI (Google Gemini) to intelligently infer optimal data types from CSV samples, generates configuration files, and manages import execution with state tracking and resume capabilities.

### Problem Statement

**Current Pain Points:**
- Manual analysis of CSV schemas is time-consuming and error-prone
- Large CSVs (GB-scale) are difficult to inspect and type manually
- pgloader configuration requires deep knowledge of data types
- Failed imports on large datasets waste significant time
- No standardized way to handle heterogeneous CSV collections

**Target Outcome:**
- Automated type inference for any CSV structure
- Repeatable, version-controlled import configurations
- Robust import process with failure recovery
- Clear audit trail of import operations

---

## Phase 1: Foundation (Week 1)

### 1.1 Project Bootstrap
**Owner:** DevOps/Setup
**Deliverables:**
- [ ] Initialize repository with UV-based Python project
- [ ] Create `pyproject.toml` with dependencies
- [ ] Set up directory structure (see CLAUDE.md)
- [ ] Configure pre-commit hooks (ruff, mypy, black)
- [ ] Create `.env.template` for API keys
- [ ] Write initial README.md with quickstart

**Dependencies:** None
**Acceptance Criteria:**
- `uv sync` successfully installs all dependencies
- `uv run pytest` runs (even if no tests exist yet)
- Project structure matches architecture specification

### 1.2 Configuration System
**Owner:** Core Infrastructure
**Deliverables:**
- [ ] `config.py`: Pydantic Settings model
- [ ] `config/default.yaml`: Default configuration
- [ ] Environment variable override support
- [ ] Configuration validation logic

**Config Schema:**
```yaml
sampling:
  rows: 100
  encoding: "utf-8"
  
chunking:
  columns_per_chunk: 20
  parallel_requests: true
  
llm:
  provider: "gemini"
  model: "gemini-1.5-pro"
  timeout: 30
  retry_attempts: 3
  retry_delay: 5
  
database:
  connection_template: "postgresql://{user}:{password}@{host}:{port}/{dbname}"
  
output:
  directory: "./output"
  dry_run: false
```

**Acceptance Criteria:**
- Configuration loads from file and env vars
- Invalid config raises clear validation errors
- Can override any setting via CLI flags

### 1.3 Type System Foundation
**Owner:** Core Logic
**Deliverables:**
- [ ] `types.py`: Define core data types
  - `ColumnSample` (name, values, nulls)
  - `InferredType` (pg_type, confidence, reasoning)
  - `ColumnSchema` (name, type, constraints)
  - `TableSchema` (columns, primary_key)
- [ ] PostgreSQL type mapping utilities
- [ ] Type conversion validation functions

**Acceptance Criteria:**
- All types have Pydantic models with validation
- Type conversions handle edge cases (None, empty strings)
- Documentation includes examples for each type

---

## Phase 2: CSV Processing (Week 2)

### 2.1 CSV Sampler
**Owner:** Data Processing
**Deliverables:**
- [ ] `sampler.py`: CSV sampling implementation
- [ ] Support for multiple delimiters (auto-detect)
- [ ] Encoding detection (chardet/charset-normalizer)
- [ ] Header extraction and validation
- [ ] Stratified sampling for large files
- [ ] Handle malformed CSVs gracefully

**Key Functions:**
```python
def sample_csv(
    path: Path, 
    n_rows: int = 100,
    encoding: str | None = None,
    delimiter: str | None = None
) -> CSVSample:
    """
    Returns: CSVSample with headers + sampled rows
    """

def detect_csv_properties(path: Path) -> CSVProperties:
    """
    Returns: delimiter, encoding, quote_char, has_header
    """
```

**Edge Cases to Handle:**
- Very wide CSVs (1000+ columns)
- Unicode in headers and data
- Inconsistent delimiters
- Missing headers
- Empty files

**Acceptance Criteria:**
- Handles CSVs from 1KB to 10GB
- Detects common encodings (UTF-8, Latin-1, Windows-1252)
- Sampling completes in <5 seconds for 1GB files
- Unit tests cover 10+ edge cases

### 2.2 Column Chunker
**Owner:** Data Processing
**Deliverables:**
- [ ] `chunker.py`: Column batching logic
- [ ] Configurable chunk size
- [ ] Smart chunking (keep related columns together if possible)
- [ ] Chunk metadata (chunk_id, total_chunks, columns)

**Key Functions:**
```python
def chunk_columns(
    sample: CSVSample,
    chunk_size: int = 20
) -> list[ColumnChunk]:
    """
    Returns: List of column chunks with metadata
    """
```

**Chunking Strategy:**
1. Group columns by naming patterns (e.g., `identifier_*`, `location_*`)
2. Keep groups together when possible
3. Split large groups across chunks if needed
4. Ensure no chunk exceeds size limit

**Acceptance Criteria:**
- Chunks don't exceed specified size
- All columns are included exactly once
- Chunk order is deterministic (same input → same chunks)
- Works with 1 to 10,000 columns

---

## Phase 3: LLM Integration (Week 3)

### 3.1 LLM Provider Interface
**Owner:** AI Integration
**Deliverables:**
- [ ] `llm/base.py`: Abstract provider protocol
- [ ] `llm/gemini.py`: Gemini implementation
- [ ] API key management (from env)
- [ ] Rate limiting and backoff logic
- [ ] Response parsing and validation

**Abstract Interface:**
```python
class LLMProvider(Protocol):
    async def infer_types(
        self, 
        chunk: ColumnChunk,
        sample_data: list[dict]
    ) -> list[InferredType]:
        """Returns type inference for each column in chunk"""

class GeminiProvider(LLMProvider):
    # Implementation with error handling, retries, etc.
```

**Gemini Prompt Structure:**
```
You are a database schema expert. Analyze these CSV columns and 
suggest optimal PostgreSQL data types.

Columns: [list of column names]
Sample data (first 100 rows):
[formatted sample data]

For each column, return JSON:
{
  "column_name": "identifier_uuid",
  "postgresql_type": "uuid",
  "confidence": "high",
  "reasoning": "Values match UUID pattern (8-4-4-4-12 hex digits)",
  "nullable": true,
  "constraints": ["PRIMARY KEY"]
}

Consider: null handling, precision requirements, integer vs bigint, 
text vs varchar, timestamp with/without timezone.
```

**Acceptance Criteria:**
- Abstract interface supports multiple providers (future: OpenAI, Claude)
- Gemini integration handles API errors gracefully
- Responses are validated against expected schema
- Rate limiting prevents API abuse
- Comprehensive logging of API interactions

### 3.2 Type Inference Orchestrator
**Owner:** AI Integration
**Deliverables:**
- [ ] `inference.py`: Orchestration logic
- [ ] Parallel chunk processing
- [ ] Result merging and validation
- [ ] Fallback to heuristic inference on API failure
- [ ] Confidence scoring across chunks

**Key Functions:**
```python
async def infer_schema(
    sample: CSVSample,
    provider: LLMProvider,
    chunk_size: int = 20
) -> TableSchema:
    """
    Orchestrates:
    1. Chunk columns
    2. Parallel API calls
    3. Merge results
    4. Validate consistency
    5. Return complete schema
    """

def heuristic_type_inference(
    column: ColumnSample
) -> InferredType:
    """Fallback: pattern matching and heuristics"""
```

**Heuristic Rules (Fallback):**
- UUID pattern → `uuid`
- Date patterns → `date` or `timestamptz`
- Integer values → `integer` or `bigint` (based on max value)
- Decimal values → `numeric`
- Email pattern → `text` (with note for validation)
- Default → `text`

**Acceptance Criteria:**
- Processes 100-column CSV in <30 seconds
- Handles API failures without crashing
- Merges results from 5+ chunks correctly
- Confidence scores are meaningful and documented
- Logs detailed reasoning for each type decision

---

## Phase 4: Code Generation (Week 4)

### 4.1 Template System
**Owner:** Code Generation
**Deliverables:**
- [ ] `templates/pgloader.jinja2`: pgloader config template
- [ ] `templates/import.sh.jinja2`: Bash script template
- [ ] Template validation utilities
- [ ] Example templates for common scenarios

**pgloader Template Structure:**
```jinja2
LOAD CSV
    FROM '{{ csv_path }}'
    INTO {{ database_url }}
    
    WITH
        truncate,
        skip header = 1,
        fields optionally enclosed by '"',
        fields escaped by double-quote,
        fields terminated by '{{ delimiter }}'
    
    SET
        work_mem to '256MB',
        maintenance_work_mem to '512MB'
    
    BEFORE LOAD DO
    $$ DROP TABLE IF EXISTS {{ table_name }}; $$,
    $$ CREATE TABLE {{ table_name }} (
        {%- for column in columns %}
        {{ column.name }} {{ column.pg_type }}
        {%- if column.constraints %} {{ column.constraints|join(' ') }}{% endif %}
        {%- if not loop.last %},{% endif %}
        {%- endfor %}
    ); $$
    
    CAST
        {%- for column in columns if column.needs_cast %}
        {{ column.name }} to {{ column.pg_type }} using {{ column.cast_rule }}
        {%- if not loop.last %},{% endif %}
        {%- endfor %}
;
```

**Bash Script Template:**
```jinja2
#!/bin/bash
set -euo pipefail

# Generated by CSV2PG on {{ generation_date }}
# CSV: {{ csv_path }}
# Table: {{ table_name }}

STATE_FILE="{{ state_file }}"
LOG_FILE="{{ log_file }}"

# Load state if exists
if [[ -f "$STATE_FILE" ]]; then
    STATUS=$(jq -r '.status' "$STATE_FILE")
    if [[ "$STATUS" == "completed" ]]; then
        echo "Import already completed. Use --force to reimport."
        exit 0
    fi
fi

# Update state: starting
jq -n \
    --arg status "in_progress" \
    --arg start "$(date -Iseconds)" \
    '{status: $status, start_time: $start}' \
    > "$STATE_FILE"

# Run pgloader
if pgloader {{ pgloader_config }} >> "$LOG_FILE" 2>&1; then
    jq -n \
        --arg status "completed" \
        --arg end "$(date -Iseconds)" \
        '{status: $status, end_time: $end}' \
        > "$STATE_FILE"
    echo "Import completed successfully"
    exit 0
else
    jq -n \
        --arg status "failed" \
        --arg end "$(date -Iseconds)" \
        '{status: $status, end_time: $end}' \
        > "$STATE_FILE"
    echo "Import failed. Check $LOG_FILE"
    exit 1
fi
```

**Acceptance Criteria:**
- Templates render without Jinja2 errors
- Generated pgloader configs are syntactically valid
- Bash scripts are shellcheck-compliant
- All templates support dry-run mode (validation only)

### 4.2 Generator Module
**Owner:** Code Generation
**Deliverables:**
- [ ] `generator.py`: File generation logic
- [ ] Output directory management
- [ ] File naming conventions
- [ ] Overwrite protection
- [ ] Dry-run mode

**Key Functions:**
```python
def generate_pgloader_config(
    schema: TableSchema,
    csv_path: Path,
    output_dir: Path,
    database_url: str
) -> Path:
    """Generates .load file, returns path"""

def generate_import_script(
    config_path: Path,
    state_file: Path,
    output_dir: Path
) -> Path:
    """Generates .sh file, returns path"""

def generate_all(
    schema: TableSchema,
    csv_path: Path,
    output_dir: Path,
    database_url: str,
    dry_run: bool = False
) -> GenerationResult:
    """Orchestrates all generation, returns file paths"""
```

**File Naming Convention:**
```
organizations.csv → 
  output/organizations.load
  output/organizations_import.sh
  output/organizations_state.json
  output/organizations_import.log
```

**Acceptance Criteria:**
- Generated files follow naming convention
- Dry-run mode shows output without writing files
- Prevents accidental overwrites (requires --force flag)
- All generated files are logged

---

## Phase 5: State Management (Week 5)

### 5.1 State Tracking
**Owner:** Orchestration
**Deliverables:**
- [ ] `state_manager.py`: State persistence
- [ ] JSON state file format
- [ ] Atomic writes (temp + rename)
- [ ] State validation
- [ ] Resume logic

**State File Schema:**
```json
{
  "version": "1.0",
  "csv_path": "/path/to/organizations.csv",
  "csv_checksum": "sha256:abc123...",
  "table_name": "organizations",
  "status": "in_progress",
  "phase": "importing",
  "timestamps": {
    "started": "2025-09-30T10:00:00Z",
    "sampled": "2025-09-30T10:00:05Z",
    "inferred": "2025-09-30T10:00:35Z",
    "generated": "2025-09-30T10:00:36Z",
    "import_started": "2025-09-30T10:00:40Z",
    "completed": null
  },
  "progress": {
    "rows_loaded": 1234567,
    "rows_total": 5000000,
    "percent": 24.7
  },
  "error": null
}
```

**State Transitions:**
```
null → sampling → sampled → inferring → inferred → 
generating → generated → importing → completed
                                      ↘ failed
```

**Key Functions:**
```python
class StateManager:
    def save_state(self, state: ImportState) -> None:
        """Atomically saves state to JSON file"""
    
    def load_state(self, state_file: Path) -> ImportState:
        """Loads and validates state"""
    
    def can_resume(self, state: ImportState) -> bool:
        """Checks if import can be resumed"""
    
    def mark_phase(self, phase: Phase) -> None:
        """Updates current phase and timestamp"""
```

**Acceptance Criteria:**
- State writes are atomic (no partial writes)
- State file validates against schema
- Resume logic correctly identifies resumable states
- Corrupted state files are detected and reported

### 5.2 Resume Logic
**Owner:** Orchestration
**Deliverables:**
- [ ] Resume command in CLI
- [ ] State compatibility checking
- [ ] Partial progress preservation
- [ ] Force restart option

**Resume Decision Tree:**
```
Load state file
├─ Status: completed → Skip (unless --force)
├─ Status: failed → Retry from last successful phase
├─ Status: in_progress
│  ├─ Phase: importing → Resume pgloader (if supported)
│  └─ Other phases → Restart from that phase
└─ Status: invalid/missing → Fresh start
```

**Acceptance Criteria:**
- Resume command successfully continues failed imports
- Checksum validation prevents wrong file resume
- Clear messaging about resume vs restart
- --force flag allows override

---

## Phase 6: CLI & Integration (Week 6)

### 6.1 Command Line Interface
**Owner:** User Experience
**Deliverables:**
- [ ] `cli.py`: Typer-based CLI
- [ ] Commands: `import`, `resume`, `validate`, `dry-run`
- [ ] Rich output formatting (tables, progress bars)
- [ ] Verbose/quiet modes
- [ ] Help documentation

**Command Structure:**
```bash
# Main import command
csv2pg import <CSV_PATH> [OPTIONS]
  --sample-rows N          # Default: 100
  --chunk-size N           # Default: 20
  --db-url URL             # Or from config/env
  --table-name NAME        # Default: CSV filename
  --output-dir PATH        # Default: ./output
  --dry-run                # Generate configs only
  --force                  # Overwrite existing files

# Resume failed import
csv2pg resume <STATE_FILE>
  --force                  # Restart from beginning

# Validate CSV
csv2pg validate <CSV_PATH>
  --show-sample            # Display sample data
  --check-encoding         # Detect encoding issues

# Dry-run analysis
csv2pg analyze <CSV_PATH>
  --sample-rows N
  --show-types             # Display inferred types
```

**Output Examples:**
```
✓ Sampling CSV... (100 rows, 157 columns)
✓ Detected encoding: UTF-8
✓ Chunking columns... (8 chunks)
✓ Inferring types... [████████████████████] 8/8 chunks
✓ Generating pgloader config...
✓ Generating import script...

Generated files:
  output/organizations.load
  output/organizations_import.sh

Next steps:
  1. Review the generated files
  2. Update database connection in organizations.load
  3. Run: bash output/organizations_import.sh
```

**Acceptance Criteria:**
- All commands have comprehensive --help
- Progress indicators for long operations
- Error messages are actionable
- Exit codes follow conventions (0=success, 1=error, 2=usage)

### 6.2 Integration Testing
**Owner:** Quality Assurance
**Deliverables:**
- [ ] End-to-end test suite
- [ ] Sample CSV fixtures (various sizes/formats)
- [ ] Mock Gemini API responses
- [ ] Docker-based PostgreSQL for tests
- [ ] CI/CD integration

**Test Scenarios:**
1. **Happy path:** Small CSV (50 cols, 1000 rows) → successful import
2. **Large CSV:** 200 cols, 1M rows → chunked processing
3. **Malformed CSV:** Inconsistent delimiters, encoding issues
4. **API failure:** Gemini rate limit → fallback to heuristics
5. **Resume:** Kill import midway → resume successfully
6. **Dry-run:** Validate without actual import

**Acceptance Criteria:**
- 90%+ code coverage
- All tests pass in CI
- Integration tests complete in <5 minutes
- Performance benchmarks documented

---

## Phase 7: Documentation & Polish (Week 7)

### 7.1 User Documentation
**Owner:** Documentation
**Deliverables:**
- [ ] README.md with quickstart
- [ ] USAGE.md with detailed examples
- [ ] CONFIGURATION.md explaining all options
- [ ] TROUBLESHOOTING.md for common issues
- [ ] API documentation (Sphinx or mkdocs)

**Documentation Sections:**
1. **Installation:** UV setup, dependency installation
2. **Quickstart:** 5-minute tutorial
3. **Configuration:** All config options explained
4. **CLI Reference:** Every command and flag
5. **Templates:** How to customize templates
6. **Troubleshooting:** Common errors and solutions
7. **Architecture:** High-level system design
8. **Contributing:** Guidelines for contributors

**Acceptance Criteria:**
- New user can import their first CSV in <10 minutes
- All commands documented with examples
- Common issues have documented solutions

### 7.2 CI/CD Pipeline
**Owner:** DevOps
**Deliverables:**
- [ ] GitHub Actions workflow
- [ ] Automated testing on push/PR
- [ ] Code quality checks (ruff, mypy, black)
- [ ] Coverage reporting
- [ ] Release automation

**GitHub Actions Workflow:**
```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Install dependencies
        run: uv sync --all-extras --dev
      - name: Run tests
        run: uv run pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
  
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run ruff check .
      - run: uv run mypy src/
      - run: uv run black --check .
  
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Run integration tests
        run: uv run pytest tests/integration/
```

**Acceptance Criteria:**
- CI runs on every push and PR
- All checks must pass before merge
- Coverage reports uploaded to Codecov
- Failed tests show clear error messages

---

## Phase 8: Future Enhancements (Post-MVP)

### 8.1 Advanced Features
**Priority: Medium**
- [ ] Web UI for monitoring imports
- [ ] Schema evolution (detect column changes)
- [ ] Incremental imports (append/upsert modes)
- [ ] Data quality reports
- [ ] Multiple output formats (SQLAlchemy, Alembic migrations)
- [ ] Support for other LLMs (OpenAI, Anthropic)

### 8.2 Performance Optimizations
**Priority: Low**
- [ ] Parallel CSV sampling
- [ ] Caching of type inference results
- [ ] Streaming import progress updates
- [ ] Adaptive chunk sizing based on column complexity

### 8.3 Enterprise Features
**Priority: Low**
- [ ] Multi-database support (MySQL, SQLite)
- [ ] Role-based access control
- [ ] Audit logging
- [ ] Scheduled imports
- [ ] Integration with data catalogs

---

## Risk Management

### Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Gemini API rate limits | High | Medium | Implement exponential backoff, fallback heuristics |
| Large CSV OOM errors | High | Low | Use streaming/chunked processing with Polars |
| pgloader unavailable | Medium | Low | Document installation, provide Docker option |
| Type inference errors | Medium | Medium | Extensive testing, confidence scoring, manual review option |
| State file corruption | Low | Low | Atomic writes, validation on load |

### Timeline Risks

| Risk | Mitigation |
|------|------------|
| LLM integration complexity | Start with simple prompts, iterate |
| Template generation edge cases | Build test suite first with diverse CSVs |
| CI/CD setup delays | Use standard GitHub Actions, minimal customization |

---

## Success Metrics

### MVP Success Criteria
- [ ] Successfully imports 10+ diverse CSV files
- [ ] Type inference accuracy >85%
- [ ] Handles CSVs up to 10GB
- [ ] Resume functionality works reliably
- [ ] Documentation enables onboarding in <30 minutes
- [ ] CI pipeline runs tests in <10 minutes

### Performance Targets
- **Sampling:** <5 seconds for 1GB CSV
- **Type inference:** <30 seconds for 100 columns
- **Config generation:** <1 second
- **End-to-end:** <2 minutes for analysis phase

### Quality Targets
- **Test coverage:** >90%
- **Type accuracy:** >85% match with expert judgment
- **Documentation:** All public APIs documented
- **Code quality:** Passes ruff, mypy with strict mode

---

## Team Structure

**Recommended Roles:**
- **Core Infrastructure:** Configuration, types, utilities (1 dev, 1 week)
- **Data Processing:** Sampler, chunker (1 dev, 1 week)
- **AI Integration:** LLM interface, inference (1 dev, 1 week)
- **Code Generation:** Templates, generator (1 dev, 1 week)
- **Orchestration:** State management, CLI (1 dev, 1 week)
- **Quality Assurance:** Testing, CI/CD (1 dev, 2 weeks)
- **Documentation:** User guide, API docs (1 dev, 1 week)

**Total Effort:** 8 person-weeks for MVP

---

## Appendix

### Dependencies Rationale

- **UV:** Fastest Python package manager, excellent for CLI tools
- **Polars:** 10-100x faster than pandas for large CSVs
- **Pydantic:** Best-in-class validation, great with modern Python
- **Typer:** Beautiful CLIs with minimal code
- **Jinja2:** Industry-standard templating
- **google-generativeai:** Official Gemini SDK

### Alternative Approaches Considered

1. **Use pandas instead of polars:** Rejected due to memory issues with large files
2. **Use Alembic migrations instead of pgloader:** Rejected for complexity, pgloader is purpose-built
3. **Use OpenAI instead of Gemini:** Could be added later, Gemini chosen for cost
4. **Build web UI first:** Rejected, CLI is faster to build and more flexible

### Open Questions

1. Should we support CSV files with multiple tables (e.g., denormalized data)?
2. Do we need support for compressed CSVs (gzip, bz2)?
3. Should we validate data against the inferred schema before import?
4. Do we need multi-tenancy (different API keys per user)?
```


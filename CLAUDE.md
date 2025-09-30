# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CSV2PG is an automated pipeline for intelligently importing large CSV files into PostgreSQL via pgloader. The system uses Google Gemini AI to infer optimal PostgreSQL data types by analyzing CSV samples, then generates pgloader configuration files and bash import scripts with state management and resume capabilities.

**Key Components:**
- CSV sampling and analysis
- LLM-powered type inference via Gemini API
- pgloader configuration generation
- Stateful import orchestration with resume support
- Modular, plugin-based architecture

**Target Users:** Data engineers working with large (multi-GB) CSV datasets who need reliable, repeatable imports into Supabase/PostgreSQL.

## Current State

This is a newly initialized repository. No code, build system, or development infrastructure has been established yet. The project is in the planning phase with comprehensive documentation already created in PLAN.md and TESTS.md.

## Technology Stack

- **Language:** Python 3.12+
- **Package Manager:** UV (for dependency management and task running)
- **Key Dependencies:**
  - `google-generativeai` - Gemini API integration
  - `polars` - High-performance CSV sampling for large files
  - `pydantic` - Data validation and settings management
  - `jinja2` - Template rendering for config files
  - `typer` - CLI framework
  - `pyyaml` - Configuration file parsing
  - `sqlalchemy` - Database type mapping
- **External Tools:** pgloader (for actual data import)
- **Testing:** pytest, pytest-cov, pytest-asyncio
- **CI/CD:** GitHub Actions

## Development Commands

Once the project is set up, common commands will be:

```bash
# Install dependencies
uv sync

# Run the CLI
uv run csv2pg import <CSV_FILE>

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=html

# Run linting
uv run ruff check src/ tests/
uv run mypy src/
uv run black src/ tests/

# Run integration tests
uv run pytest tests/integration/

# Run performance benchmarks
uv run pytest tests/performance/ --benchmark-only
```

## Architecture

### Modularity

Each component should be independently testable and replaceable:

- **Sampler:** CSV reading and sampling logic
- **Chunker:** Column batching strategy (breaks wide CSVs into manageable chunks for LLM API)
- **LLM Interface:** Abstract base class with provider-specific implementations (currently Gemini)
- **Type Inference:** Orchestration of LLM calls and result merging across chunks
- **Template Generator:** File generation from Jinja2 templates (pgloader configs, bash scripts)
- **State Manager:** Import progress tracking and resume logic

### Planned Directory Structure

```
src/csv2pg/
├── __init__.py           # Package initialization
├── cli.py                # Typer-based CLI entry point
├── config.py             # Configuration management (Pydantic settings)
├── sampler.py            # CSV sampling logic
├── chunker.py            # Column batching
├── llm/
│   ├── __init__.py
│   ├── base.py          # Abstract LLM provider interface
│   └── gemini.py        # Gemini implementation
├── inference.py          # Type inference orchestration
├── generator.py          # Config/script generation
├── state_manager.py      # Import state tracking
├── types.py              # Type definitions and mappings
├── templates/
│   ├── pgloader.jinja2
│   └── import.sh.jinja2
└── utils/
    ├── __init__.py
    ├── validation.py     # Response validation
    └── logger.py         # Logging setup
```

## Key Design Principles

### Configuration Over Code
- Use YAML/TOML for user-configurable settings
- Environment variables for secrets (API keys)
- Sensible defaults in `config/default.yaml`
- Allow CLI flag overrides

### Error Handling
- Graceful degradation: if Gemini API fails, fall back to heuristic type detection
- Comprehensive logging at DEBUG, INFO, WARN, ERROR levels
- Clear error messages with actionable suggestions
- Retry logic with exponential backoff for API calls

### Performance Considerations
- Use `polars` for CSV operations (faster than pandas for large files)
- Parallel API calls for column chunks when possible
- Streaming processing where applicable
- Lazy evaluation for memory efficiency

## CLI Design

The primary interface should be intuitive:

```bash
# Basic usage
uv run csv2pg import organizations.csv

# With options
uv run csv2pg import organizations.csv \
  --sample-rows 200 \
  --chunk-size 15 \
  --db-url postgresql://... \
  --dry-run

# Resume failed import
uv run csv2pg resume organizations_state.json

# Validate CSV structure
uv run csv2pg validate organizations.csv
```

## Implementation Guidelines

### When Implementing Features

1. **Start with types:** Define Pydantic models for data structures first
2. **Write tests first:** Use TDD approach for core logic
3. **Use protocols:** Define interfaces before implementations
4. **Document as you go:** Docstrings with examples for all public functions
5. **Handle edge cases:** Empty files, single column CSVs, Unicode issues, etc.

### Template System

Templates should be:
- Clean and readable (avoid complex logic in Jinja2)
- Well-commented with placeholders clearly marked
- Support variable substitution for all configurable values
- Include validation markers for generated configs

### State Management

State files should:
- Be JSON for easy inspection and debugging
- Include timestamps for all phase transitions
- Track both success and failure states
- Be atomic (write to temp, then rename)
- Include enough context for resume without re-analysis

### Testing Strategy

- **Unit tests:** Each module in isolation with mocked dependencies
- **Integration tests:** End-to-end with sample CSVs (various sizes/formats)
- **API tests:** Mock Gemini responses for deterministic testing
- **Property tests:** Use hypothesis for edge case discovery
- **Performance tests:** Benchmark with 1MB, 100MB, 1GB sample files

### Logging

Use structured logging:
```python
logger.info("csv_sampled",
    csv_path=path,
    rows_sampled=100,
    columns=50,
    duration_ms=duration
)
```

## Common Pitfalls to Avoid

1. **Don't load entire CSVs into memory** - Use streaming/chunked reading
2. **Don't assume CSV structure** - Validate headers, detect delimiters
3. **Don't trust LLM responses blindly** - Validate against expected schema
4. **Don't hardcode paths** - Use Path objects and make everything configurable
5. **Don't ignore encoding issues** - Detect and handle various encodings
6. **Don't skip the dry-run mode** - Always allow users to preview before execution
7. **Don't forget Windows compatibility** - Test path handling cross-platform

## Related Documentation

- **PLAN.md**: Detailed project roadmap with phases, deliverables, and timelines (7 weeks to MVP)
- **TESTS.md**: Comprehensive testing strategy with specific test cases and CI/CD workflows
- **README.md**: User-facing documentation (to be created during Phase 7)

## Next Steps for Implementation

Based on PLAN.md, the recommended implementation sequence is:

1. **Bootstrap project:** Set up pyproject.toml with UV, create directory structure
2. **Implement sampler:** CSV reading with polars, handle edge cases
3. **Implement LLM interface:** Abstract base + Gemini provider
4. **Build type inference:** Orchestrate chunking and API calls
5. **Create templates:** pgloader and bash script templates
6. **Implement CLI:** Typer-based interface with all commands
7. **Add state management:** JSON-based progress tracking
8. **Integration tests:** End-to-end testing with real CSVs
9. **Documentation:** User guide, API docs, examples
10. **CI/CD:** GitHub Actions for testing and linting
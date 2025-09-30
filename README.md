# csv2pg-ai-schema-infer

AI-powered tool that automatically infers PostgreSQL schemas from CSV files and generates optimized pgloader configurations for fast, reliable imports.

## Features

- 🧠 **Intelligent Type Inference** - Uses Google Gemini to analyze CSV samples and suggest optimal PostgreSQL types
- 📊 **Large File Support** - Handles multi-GB CSVs efficiently with streaming processing
- 🔄 **Resume Capability** - Automatic state tracking with resume support for failed imports
- ⚡ **Fast Imports** - Leverages pgloader for high-performance bulk loading
- 🎯 **Zero Configuration** - Works out of the box with sensible defaults
- 🔧 **Fully Customizable** - Override any setting via config file or CLI flags
- 🔍 **Heuristic Fallback** - Works without AI when API is unavailable

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/SEBK4C/csv2pg-ai-schema-infer.git
cd csv2pg-ai-schema-infer

# Install with UV
uv sync

# Set Gemini API key (optional, but recommended)
export GEMINI_API_KEY="your-api-key-here"
```

### Basic Usage

```bash
# Validate CSV structure
uv run csv2pg-ai-schema-infer validate organizations.csv --show-sample

# Import CSV with AI-powered type inference
uv run csv2pg-ai-schema-infer import-csv organizations.csv \\
  --db-url postgresql://user:pass@localhost:5432/mydb

# Import without AI (heuristic inference only)
uv run csv2pg-ai-schema-infer import-csv organizations.csv \\
  --db-url postgresql://user:pass@localhost:5432/mydb \\
  --no-llm

# Dry run (generate configs without importing)
uv run csv2pg-ai-schema-infer import-csv organizations.csv \\
  --db-url postgresql://user:pass@localhost:5432/mydb \\
  --dry-run
```

## Commands

### `validate`

Validate CSV file structure and properties.

```bash
uv run csv2pg-ai-schema-infer validate <CSV_FILE> [OPTIONS]

Options:
  --show-sample, -s    Display sample data
  --check-encoding, -e Detect encoding issues
```

### `import-csv`

Import CSV file into PostgreSQL with AI-powered schema inference.

```bash
uv run csv2pg-ai-schema-infer import-csv <CSV_FILE> [OPTIONS]

Options:
  --sample-rows, -n N       Number of rows to sample (default: 100)
  --chunk-size, -c N        Columns per chunk for LLM (default: 20)
  --db-url, -d URL          PostgreSQL connection URL
  --table-name, -t NAME     Target table name (default: CSV filename)
  --output-dir, -o PATH     Output directory (default: ./output)
  --dry-run                 Generate configs without importing
  --force, -f               Overwrite existing files
  --no-llm                  Skip LLM inference, use heuristics only
  --verbose                 Enable verbose logging
```

### `resume`

Resume a failed or interrupted import (not yet fully implemented).

```bash
uv run csv2pg-ai-schema-infer resume <STATE_FILE> [OPTIONS]

Options:
  --force, -f              Force restart from beginning
```

## Configuration

### Environment Variables

```bash
# Required for AI inference
GEMINI_API_KEY=your-gemini-api-key

# Database connection (or use --db-url)
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# Optional overrides
CSV2PG_SAMPLING_ROWS=100
CSV2PG_CHUNKING_COLUMNS_PER_CHUNK=20
CSV2PG_OUTPUT_DIRECTORY=./output
```

### Configuration File

Create `config/default.yaml`:

```yaml
sampling:
  rows: 100
  encoding: "utf-8"

chunking:
  columns_per_chunk: 20
  parallel_requests: true

llm:
  provider: "gemini"
  model: "gemini-2.5-pro"
  timeout: 30
  retry_attempts: 3
  retry_delay: 5

database:
  connection_template: "postgresql://{user}:{password}@{host}:{port}/{dbname}"

output:
  directory: "./output"
  dry_run: false
```

## How It Works

1. **Sample CSV** - Reads first N rows to understand structure
2. **Detect Properties** - Auto-detects delimiter, encoding, headers
3. **Chunk Columns** - Splits wide CSVs into manageable chunks
4. **Infer Types** - Uses AI (or heuristics) to suggest PostgreSQL types
5. **Generate Config** - Creates pgloader configuration file
6. **Generate Script** - Creates bash import script with state management
7. **Execute Import** - Run the generated script to import data

## Generated Files

For a CSV named `organizations.csv`, the tool generates:

- `output/organizations.load` - pgloader configuration
- `output/organizations_import.sh` - bash import script
- `output/organizations_state.json` - state tracking file
- `output/organizations_import.log` - import log file

## Example Output

```
CSV2PG AI Schema Infer

CSV File: organizations.csv
Table Name: organizations
Output Dir: output

✓ Sampled 100 rows, 157 columns
✓ Inferred types for 157 columns
✓ Generated configuration files

Inferred Schema:

┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Column             ┃ Type        ┃ Nullable ┃ Constraints ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ identifier_uuid    │ uuid        │ ✗        │ PRIMARY KEY │
│ identifier_id      │ integer     │ ✗        │             │
│ identifier_type    │ varchar(50) │ ✗        │             │
│ name               │ text        │ ✗        │             │
│ created_at         │ timestamptz │ ✗        │             │
│ ...                │ ...         │ ...      │ ...         │
└────────────────────┴─────────────┴──────────┴─────────────┘

Generated Files:
  • pgloader config: output/organizations.load
  • Import script:   output/organizations_import.sh
  • State file:      output/organizations_state.json
  • Log file:        output/organizations_import.log

Next Steps:
  1. Review the generated files
  2. Verify the database connection URL
  3. Run the import: bash output/organizations_import.sh

✓ Import preparation complete!
```

## Type Inference

The tool uses a two-tier approach:

### AI-Powered Inference (Gemini)

When Gemini API key is available, the tool:
- Sends column samples to Gemini API
- Receives intelligent type suggestions
- Considers null handling, precision, constraints
- Provides reasoning for each type choice

### Heuristic Fallback

When AI is unavailable or disabled with `--no-llm`:
- UUID pattern detection
- Date/timestamp pattern matching
- Integer vs bigint based on value range
- Decimal/numeric for floating point
- Boolean pattern recognition
- Email pattern detection
- Default to text/varchar

## Dependencies

- **Python 3.12+**
- **UV** - Fast Python package manager
- **pgloader** - For actual data import (must be installed separately)

### Installing pgloader

```bash
# macOS
brew install pgloader

# Ubuntu/Debian
sudo apt-get install pgloader

# Docker
docker pull dimitri/pgloader
```

## Development

### Running Tests

```bash
# Install dev dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_sampler.py -v
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/

# Type checking
uv run mypy src/
```

## Project Structure

```
csv2pg-ai-schema-infer/
├── src/csv2pg_ai_schema_infer/
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # Typer-based CLI
│   ├── config.py             # Configuration management
│   ├── sampler.py            # CSV sampling
│   ├── chunker.py            # Column batching
│   ├── inference.py          # Type inference orchestration
│   ├── generator.py          # Config/script generation
│   ├── state_manager.py      # Import state tracking
│   ├── types.py              # Type definitions
│   ├── llm/
│   │   ├── base.py           # Abstract LLM interface
│   │   └── gemini.py         # Gemini implementation
│   ├── utils/
│   │   ├── validation.py     # Response validation
│   │   └── logger.py         # Logging setup
│   └── templates/
│       ├── pgloader.jinja2   # pgloader template
│       └── import.sh.jinja2  # Bash script template
├── tests/                    # Test suite
├── config/                   # Configuration files
├── pyproject.toml            # Project metadata
└── README.md                 # This file
```

## Troubleshooting

### Common Issues

**"Gemini API key not found"**
- Set `GEMINI_API_KEY` environment variable
- Or use `--no-llm` flag for heuristic inference only

**"pgloader is not installed"**
- Install pgloader: https://pgloader.io/
- Or use Docker: `docker pull dimitri/pgloader`

**"Failed to detect delimiter"**
- Manually specify delimiter with custom config
- Check if file is actually CSV format

**"CSV file is empty"**
- Ensure file has data rows (not just headers)
- Check file encoding

### Getting Help

- File an issue: https://github.com/SEBK4C/csv2pg-ai-schema-infer/issues
- Check documentation: [PLAN.md](PLAN.md), [TESTS.md](TESTS.md)
- Read the code: [CLAUDE.md](CLAUDE.md)

## Roadmap

See [PLAN.md](PLAN.md) for detailed roadmap. Key planned features:

- **Phase 8** (Post-MVP):
  - Web UI for monitoring imports
  - Schema evolution detection
  - Incremental imports (append/upsert)
  - Data quality reports
  - Support for other LLMs (OpenAI, Anthropic)
  - Multi-database support

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Acknowledgments

- Built with [UV](https://github.com/astral-sh/uv)
- Powered by [Google Gemini](https://ai.google.dev/)
- Uses [pgloader](https://pgloader.io/) for bulk imports
- Built with [Polars](https://www.pola.rs/) for fast CSV processing

---

**Made with ❤️ for data engineers who love automation**
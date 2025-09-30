# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-09-30

### Added

- Initial release of csv2pg-ai-schema-infer
- AI-powered type inference using Google Gemini API
- Heuristic fallback for type inference when AI is unavailable
- CSV sampling and property detection (delimiter, encoding, headers)
- Column chunking for wide CSVs
- pgloader configuration file generation
- Bash import script generation with state management
- State tracking for import operations
- CLI commands: `import-csv`, `validate`, `resume`
- Support for various data types:
  - UUID, integers (int/bigint), numeric/decimal
  - Date, timestamp with timezone
  - Boolean, text/varchar
  - Email detection
- Configuration via YAML file and environment variables
- Comprehensive test suite with 13+ unit tests
- GitHub Actions CI/CD workflows
- Documentation: README, PLAN, TESTS, CLAUDE markdown files

### Features

- 🧠 Intelligent type inference with confidence scoring
- 📊 Large file support via streaming with Polars
- 🔄 Resume capability with state management
- ⚡ Fast imports via pgloader
- 🎯 Zero configuration with sensible defaults
- 🔧 Fully customizable via CLI flags and config files
- 🔍 Heuristic fallback when AI unavailable

### Dependencies

- Python 3.12+
- google-generativeai >= 0.8.0
- polars >= 0.20.0
- pydantic >= 2.0.0
- typer >= 0.9.0
- jinja2 >= 3.1.0
- rich >= 13.0.0
- charset-normalizer >= 3.0.0

### Known Limitations

- Resume functionality not fully implemented yet
- Only supports single-table CSVs (no denormalized data)
- Requires manual pgloader installation
- Currently only supports Gemini API (no OpenAI/Claude yet)

## [Unreleased]

### Planned Features

- Full resume implementation
- Web UI for monitoring imports
- Schema evolution detection
- Incremental imports (append/upsert modes)
- Data quality reports
- Support for other LLMs (OpenAI, Anthropic Claude)
- Multi-database support (MySQL, SQLite)
- Compressed CSV support (gzip, bz2)
- Schema validation against inferred types

---

[0.1.0]: https://github.com/SEBK4C/csv2pg-ai-schema-infer/releases/tag/v0.1.0
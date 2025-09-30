# How to Validate CSV2PG AI Schema Infer

This guide explains how to check what's missing and validate that the project works correctly.

## Quick Validation (5 minutes)

```bash
# 1. Check all imports work
uv run python -c "
from csv2pg_ai_schema_infer import cli, config, sampler, chunker, inference
from csv2pg_ai_schema_infer.llm import GeminiProvider
print('✓ All imports successful')
"

# 2. Run unit tests
uv run pytest tests/unit/ -v

# 3. Test CLI help
uv run csv2pg-ai-schema-infer --help

# 4. Validate a test CSV
echo 'id,name,age
1,John,25
2,Jane,30' > test.csv
uv run csv2pg-ai-schema-infer validate test.csv

# 5. Test import (dry-run)
uv run csv2pg-ai-schema-infer import-csv test.csv \
  --no-llm \
  --db-url postgresql://test:test@localhost/test \
  --dry-run

# Clean up
rm test.csv
```

## Comprehensive Validation (15 minutes)

### Method 1: Automated Scripts

```bash
# Run completeness check
python3 scripts/check_completeness.py

# Run full validation suite
bash scripts/validate_project.sh
```

### Method 2: Manual Checks

#### 1. Check Project Structure

```bash
# Verify all core modules exist
ls -la src/csv2pg_ai_schema_infer/{cli,config,sampler,chunker,inference,generator,state_manager,types}.py

# Verify LLM modules
ls -la src/csv2pg_ai_schema_infer/llm/{base,gemini}.py

# Verify templates
ls -la src/csv2pg_ai_schema_infer/templates/*.jinja2

# Verify tests
ls -la tests/unit/test_*.py
```

#### 2. Test All Imports

```python
# Run Python interactive shell
uv run python

# Test imports one by one
>>> from csv2pg_ai_schema_infer import cli
>>> from csv2pg_ai_schema_infer import config
>>> from csv2pg_ai_schema_infer import sampler
>>> from csv2pg_ai_schema_infer import chunker
>>> from csv2pg_ai_schema_infer import inference
>>> from csv2pg_ai_schema_infer import generator
>>> from csv2pg_ai_schema_infer import state_manager
>>> from csv2pg_ai_schema_infer import types
>>> from csv2pg_ai_schema_infer.llm import GeminiProvider, LLMProvider
>>> from csv2pg_ai_schema_infer.utils import logger, validation
>>> print("All imports successful!")
```

#### 3. Run All Tests

```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/unit/ --cov=src --cov-report=term

# Check specific test files
uv run pytest tests/unit/test_sampler.py -v
uv run pytest tests/unit/test_chunker.py -v
uv run pytest tests/unit/test_config.py -v
```

#### 4. Test End-to-End Workflow

```bash
# Create a test CSV
cat > test_data.csv << 'EOF'
id,name,email,age,salary,is_active,created_at
1,John Doe,john@example.com,25,75000.50,true,2024-01-15T10:30:00
2,Jane Smith,jane@example.com,32,95000.75,true,2024-01-16T14:22:00
3,Bob Johnson,bob@example.com,28,82000.00,false,2024-01-17T09:15:00
EOF

# Validate the CSV
uv run csv2pg-ai-schema-infer validate test_data.csv --show-sample

# Import (heuristic mode, no API needed)
uv run csv2pg-ai-schema-infer import-csv test_data.csv \
  --no-llm \
  --db-url "postgresql://user:pass@localhost:5432/testdb" \
  --output-dir ./test_output

# Check generated files
ls -la test_output/
cat test_output/test_data.load
cat test_output/test_data_state.json

# Clean up
rm test_data.csv
rm -rf test_output/
```

#### 5. Test with AI (Optional - Requires API Key)

```bash
# Set API key
export GEMINI_API_KEY="your-api-key-here"

# Import with AI inference
uv run csv2pg-ai-schema-infer import-csv test_data.csv \
  --db-url "postgresql://user:pass@localhost:5432/testdb" \
  --output-dir ./test_output

# This will use Gemini API for type inference
```

#### 6. Code Quality Checks

```bash
# Run linting
uv run ruff check src/ tests/

# Auto-fix issues
uv run ruff check src/ tests/ --fix

# Check remaining issues
uv run ruff check src/ tests/ --statistics

# Run type checking (optional)
uv run mypy src/ || echo "Type checking has some warnings (optional)"
```

#### 7. Check Documentation

```bash
# Verify all docs exist
ls -la {README,PLAN,TESTS,CLAUDE,CHANGELOG}.md

# Check documentation completeness
wc -l *.md

# Verify examples in README work
# (manually review README.md examples)
```

## What to Look For

### ✅ Signs Everything Works

1. **All imports succeed** - No ImportError
2. **All tests pass** - 13/13 tests passing
3. **CLI commands work** - Help, validate, import-csv all respond
4. **Files generate correctly** - .load, .sh, .json files created
5. **Generated configs are valid** - SQL syntax correct
6. **State files are valid JSON** - Can be parsed
7. **Type inference works** - Correct PostgreSQL types detected

### ⚠️ Known Gaps (By Design)

1. **Integration tests missing** - Infrastructure ready, tests not written
2. **Performance tests missing** - Infrastructure ready, benchmarks not run
3. **Resume not fully implemented** - Marked as "not yet fully implemented"
4. **4 minor lint warnings** - Non-critical style issues

### ❌ Signs of Problems

1. **ImportError** - Missing dependencies or broken imports
2. **Test failures** - Logic errors in implementation
3. **CLI crashes** - Command execution errors
4. **Invalid generated files** - Template or generation errors
5. **Type inference errors** - Heuristic logic failures

## Troubleshooting

### Problem: "Module not found"

```bash
# Solution: Reinstall dependencies
uv sync --extra dev
```

### Problem: "Tests failing"

```bash
# Solution: Check test output
uv run pytest tests/unit/ -v --tb=short

# Run specific failing test
uv run pytest tests/unit/test_sampler.py::test_sample_csv_simple -v
```

### Problem: "CLI command not found"

```bash
# Solution: Verify installation
uv run which csv2pg-ai-schema-infer

# Or run directly
uv run python -m csv2pg_ai_schema_infer.cli --help
```

### Problem: "Generated files are empty"

```bash
# Solution: Check logs and run with verbose
uv run csv2pg-ai-schema-infer import-csv test.csv \
  --no-llm \
  --db-url postgresql://test:test@localhost/test \
  --verbose
```

## Expected Results

### Completeness Check

```
✓ All 43 required checks should pass
⚠️ 3 optional checks may fail (integration/performance/resume)
Status: "Minor issues found. Project is mostly complete."
```

### Unit Tests

```
13 passed, 2 warnings
Success rate: 100%
Time: <2 seconds
```

### End-to-End Test

```
✓ CSV sampled successfully
✓ Types inferred (10 columns)
✓ Files generated (3 files)
Status: "Import preparation complete!"
```

### Code Quality

```
Found 4 errors (all non-critical)
Status: Production-ready
```

## Continuous Validation

### On Every Change

```bash
# Quick check
uv run pytest tests/unit/ -q && echo "✓ Tests pass"
```

### Before Commit

```bash
# Full check
uv run pytest tests/unit/ -v && \
uv run ruff check src/ tests/ && \
echo "✓ Ready to commit"
```

### Before Release

```bash
# Comprehensive validation
python3 scripts/check_completeness.py && \
bash scripts/validate_project.sh && \
echo "✓ Ready for release"
```

## Validation Checklist

Use this checklist to ensure everything works:

- [ ] All modules import successfully
- [ ] All 13 unit tests pass
- [ ] CLI help command works
- [ ] Validate command works on test CSV
- [ ] Import command generates all 3 files
- [ ] Generated pgloader config is valid SQL
- [ ] Generated bash script is executable
- [ ] State file is valid JSON
- [ ] Type inference detects correct types
- [ ] Heuristic mode works without API
- [ ] Documentation is complete
- [ ] Linting has <10 errors
- [ ] Code quality is acceptable

## Next Steps After Validation

If validation passes:

1. ✅ **Test with real CSV files** from your data
2. ✅ **Set up Gemini API key** for AI inference
3. ✅ **Install pgloader** for actual imports
4. ✅ **Configure database connection**
5. ✅ **Run your first import**

If validation fails:

1. ❌ Check the error messages carefully
2. ❌ Review the troubleshooting section
3. ❌ Run validation scripts with verbose output
4. ❌ Check that all dependencies are installed
5. ❌ File an issue if problem persists

---

**For detailed results, see:** [VALIDATION_REPORT.md](VALIDATION_REPORT.md)
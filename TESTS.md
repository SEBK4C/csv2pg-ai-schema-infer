# TESTS.md

## Testing Strategy for CSV2PG

This document outlines the comprehensive testing strategy for the CSV2PG project, covering unit tests, integration tests, performance tests, and CI/CD integration.

---

## Testing Philosophy

### Principles

1. **Test Early, Test Often:** TDD approach for core logic
2. **Fast Feedback:** Unit tests run in <10 seconds
3. **Real-World Scenarios:** Integration tests with actual CSV files
4. **Deterministic:** No flaky tests; mock external dependencies
5. **Coverage as a Guide:** Aim for >90%, but focus on critical paths
6. **Performance Awareness:** Benchmark tests for large datasets

### Test Pyramid

```
      /\
     /  \      E2E Tests (10%)
    /----\     Integration Tests (30%)
   /      \    Unit Tests (60%)
  /________\
```

---

## Unit Tests

### Coverage Areas

#### 1. Configuration (`test_config.py`)

**Test Cases:**
- [x] Load default configuration from YAML
- [x] Override config with environment variables
- [x] Validate required fields (API key, database URL)
- [x] Handle missing config file gracefully
- [x] Merge CLI flags with config file
- [x] Reject invalid configuration values

**Example Test:**
```python
def test_config_env_override():
    """Environment variables should override file config"""
    os.environ["CSV2PG_CHUNK_SIZE"] = "30"
    config = load_config("config/default.yaml")
    assert config.chunking.columns_per_chunk == 30
```

#### 2. CSV Sampler (`test_sampler.py`)

**Test Cases:**
- [x] Sample first N rows correctly
- [x] Detect delimiter (comma, tab, pipe, semicolon)
- [x] Detect encoding (UTF-8, Latin-1, Windows-1252)
- [x] Handle CSVs with BOM (byte order mark)
- [x] Handle CSVs without headers
- [x] Handle empty CSV files
- [x] Handle single-column CSVs
- [x] Handle CSVs with quoted fields containing delimiters
- [x] Handle CSVs with escaped quotes
- [x] Handle very wide CSVs (1000+ columns)
- [x] Handle CSVs with Unicode in headers and data
- [x] Stream large files without loading into memory

**Edge Cases:**
```python
def test_malformed_csv_inconsistent_columns():
    """Should handle rows with different column counts"""
    csv_content = "a,b,c\n1,2,3\n4,5\n6,7,8,9"
    sample = sample_csv_from_string(csv_content)
    # Should still parse, potentially with warnings

def test_csv_with_embedded_newlines():
    """Should handle quoted fields with newlines"""
    csv_content = 'a,b\n1,"hello\nworld"\n2,"foo"'
    sample = sample_csv_from_string(csv_content)
    assert sample.rows[0]["b"] == "hello\nworld"
```

#### 3. Column Chunker (`test_chunker.py`)

**Test Cases:**
- [x] Chunk columns into batches of specified size
- [x] Handle CSV with fewer columns than chunk size
- [x] Handle CSV with exactly chunk size columns
- [x] Ensure all columns appear in exactly one chunk
- [x] Maintain deterministic ordering (same input → same chunks)
- [x] Group related columns (by naming pattern)
- [x] Handle very large column counts (10,000+)

**Property-Based Tests:**
```python
@hypothesis.given(
    columns=st.lists(st.text(min_size=1), min_size=1, max_size=1000),
    chunk_size=st.integers(min_value=1, max_value=100)
)
def test_chunking_preserves_all_columns(columns, chunk_size):
    """Every column appears exactly once across all chunks"""
    chunks = chunk_columns(columns, chunk_size)
    flattened = [col for chunk in chunks for col in chunk.columns]
    assert sorted(flattened) == sorted(columns)
```

#### 4. Type Inference (`test_inference.py`)

**Test Cases:**
- [x] Infer integers correctly (int, bigint)
- [x] Infer decimals as numeric
- [x] Infer dates (various formats)
- [x] Infer timestamps with timezone
- [x] Infer UUIDs
- [x] Infer booleans (true/false, yes/no, 1/0)
- [x] Infer text for mixed types
- [x] Handle NULL values correctly
- [x] Detect primary key candidates
- [x] Fallback to heuristics when API fails
- [x] Merge type inferences from multiple chunks
- [x] Handle conflicting type suggestions

**Heuristic Fallback Tests:**
```python
def test_heuristic_uuid_detection():
    """Should detect UUID pattern without LLM"""
    samples = [
        "550e8400-e29b-41d4-a716-446655440000",
        "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        None
    ]
    inferred = heuristic_inference(samples)
    assert inferred.pg_type == "uuid"
    assert inferred.confidence == "high"
```

#### 5. LLM Integration (`test_llm.py`)

**Test Cases:**
- [x] Parse valid Gemini API responses
- [x] Handle API errors (rate limit, timeout, auth)
- [x] Retry with exponential backoff
- [x] Validate response schema
- [x] Handle malformed JSON responses
- [x] Mock API calls for deterministic testing
- [x] Timeout after configured duration

**Mock API Test:**
```python
@pytest.fixture
def mock_gemini_response():
    return {
        "columns": [
            {
                "name": "id",
                "postgresql_type": "uuid",
                "confidence": "high",
                "nullable": false,
                "constraints": ["PRIMARY KEY"]
            }
        ]
    }

def test_gemini_response_parsing(mock_gemini_response):
    """Should parse API response into InferredType objects"""
    provider = GeminiProvider(api_key="test")
    with patch.object(provider, '_call_api', return_value=mock_gemini_response):
        results = provider.infer_types(chunk, sample_data)
        assert len(results) == 1
        assert results[0].pg_type == "uuid"
```

#### 6. Template Generation (`test_generator.py`)

**Test Cases:**
- [x] Render pgloader config with all fields
- [x] Render bash script with state management
- [x] Escape special characters in templates
- [x] Handle tables with 1 column
- [x] Handle tables with 1000+ columns
- [x] Generate valid SQL syntax
- [x] Generate shellcheck-compliant bash
- [x] Include CAST rules for numeric types
- [x] Include constraints (PRIMARY KEY, NOT NULL)

**Validation Tests:**
```python
def test_pgloader_syntax_valid():
    """Generated pgloader config should be syntactically valid"""
    schema = create_test_schema()
    config_path = generate_pgloader_config(schema, ...)
    # Run pgloader --dry-run to validate syntax
    result = subprocess.run(
        ["pgloader", "--dry-run", str(config_path)],
        capture_output=True
    )
    assert result.returncode == 0
```

#### 7. State Management (`test_state_manager.py`)

**Test Cases:**
- [x] Save state atomically (temp + rename)
- [x] Load and validate state file
- [x] Detect corrupted state files
- [x] Determine if state is resumable
- [x] Update phase transitions
- [x] Handle concurrent writes (file locking)
- [x] Preserve state across crashes

**Atomic Write Test:**
```python
def test_atomic_state_write():
    """State writes should be atomic"""
    state = ImportState(status="in_progress", phase="importing")
    manager = StateManager(state_file="test_state.json")
    
    # Simulate crash during write
    with patch('os.rename', side_effect=OSError):
        with pytest.raises(OSError):
            manager.save_state(state)
    
    # Original file should be unchanged or not exist
    assert not manager.state_file.exists() or manager.load_state().status != "in_progress"
```

---

## Integration Tests

### Setup Requirements

- **PostgreSQL container:** For actual database operations
- **Sample CSV files:** Various sizes and formats
- **Mock HTTP server:** For API testing without real calls

**Docker Compose for Tests:**
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: csv2pg_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5432:5432"
```

### Test Scenarios

#### 1. End-to-End Happy Path (`test_e2e_happy.py`)

**Scenario:** Small CSV with clear types imports successfully

**Steps:**
1. Prepare test CSV (50 columns, 1000 rows)
2. Run `csv2pg import test.csv --db-url=...`
3. Verify pgloader config generated
4. Verify bash script generated
5. Execute import script
6. Verify data in PostgreSQL
7. Check state file shows "completed"

**Assertions:**
- All files created in output directory
- Table exists in database
- Row count matches CSV
- Data types match inferred types
- State file shows success

#### 2. Large CSV (`test_e2e_large.py`)

**Scenario:** 200 columns, 1M rows, multiple chunks

**Steps:**
1. Generate synthetic large CSV
2. Run import with parallelization enabled
3. Monitor progress via state file
4. Verify successful completion

**Performance Assertions:**
- Sampling completes in <10 seconds
- Type inference completes in <60 seconds
- Import completes in <5 minutes (with pgloader)

#### 3. Malformed CSV (`test_e2e_malformed.py`)

**Scenario:** CSV with encoding issues, inconsistent delimiters

**Steps:**
1. Prepare malformed CSV (mixed encodings, bad delimiters)
2. Run import with auto-detection
3. Verify graceful handling or clear error message

**Assertions:**
- No crashes or stack traces
- Clear error messages
- Suggestions for manual fixes

#### 4. API Failure & Recovery (`test_e2e_api_failure.py`)

**Scenario:** Gemini API fails, fallback to heuristics

**Steps:**
1. Mock Gemini API to return 429 (rate limit)
2. Run import
3. Verify fallback to heuristic inference
4. Verify warning logged
5. Verify import still completes

**Assertions:**
- Import succeeds despite API failure
- Heuristic types used
- Warning in logs about fallback

#### 5. Resume Failed Import (`test_e2e_resume.py`)

**Scenario:** Import fails midway, resume completes it

**Steps:**
1. Start import
2. Kill process during pgloader execution
3. Run `csv2pg resume <state_file>`
4. Verify completion

**Assertions:**
- Resume picks up from correct phase
- Final data is complete
- No duplicate processing

#### 6. Dry-Run Mode (`test_e2e_dry_run.py`)

**Scenario:** Generate configs without importing

**Steps:**
1. Run `csv2pg import test.csv --dry-run`
2. Verify configs generated
3. Verify no database connection attempted
4. Verify no state file created

**Assertions:**
- Config files exist and are valid
- Database untouched
- No side effects

---

## Performance Tests

### Benchmarking Suite (`test_performance.py`)

**Benchmark Scenarios:**

#### 1. Sampling Performance
```python
@pytest.mark.benchmark
def test_benchmark_sampling(benchmark):
    """Benchmark CSV sampling"""
    result = benchmark(sample_csv, large_csv_path, n_rows=100)
    # Target: <5 seconds for 1GB file
    assert benchmark.stats.median < 5.0
```

#### 2. Type Inference Performance
```python
@pytest.mark.benchmark
def test_benchmark_inference(benchmark):
    """Benchmark type inference for 100 columns"""
    result = benchmark(infer_schema, sample, provider)
    # Target: <30 seconds
    assert benchmark.stats.median < 30.0
```

#### 3. Memory Usage
```python
def test_memory_usage_large_csv():
    """Verify memory usage stays reasonable"""
    import psutil
    process = psutil.Process()
    
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    sample = sample_csv(huge_csv_path)
    final_memory = process.memory_info().rss / 1024 / 1024
    
    memory_increase = final_memory - initial_memory
    # Should not load entire file into memory
    assert memory_increase < 100  # MB
```

### Performance Targets

| Operation | Target | Maximum |
|-----------|--------|---------|
| Sample 1GB CSV | <5s | <10s |
| Infer 50 columns | <15s | <30s |
| Infer 200 columns | <30s | <60s |
| Generate config | <1s | <2s |
| Memory usage | <100MB | <500MB |

---

## Test Organization

### Directory Structure

```
tests/
├── unit/
│   ├── test_config.py
│   ├── test_sampler.py
│   ├── test_chunker.py
│   ├── test_inference.py
│   ├── test_llm.py
│   ├── test_generator.py
│   └── test_state_manager.py
├── integration/
│   ├── test_e2e_happy.py
│   ├── test_e2e_large.py
│   ├── test_e2e_malformed.py
│   ├── test_e2e_api_failure.py
│   ├── test_e2e_resume.py
│   └── test_e2e_dry_run.py
├── performance/
│   └── test_performance.py
├── fixtures/
│   ├── sample_csvs/
│   │   ├── simple.csv
│   │   ├── unicode.csv
│   │   ├── malformed.csv
│   │   ├── wide.csv (1000 columns)
│   │   └── large.csv (generated)
│   ├── mock_responses/
│   │   └── gemini_responses.json
│   └── schemas/
│       └── expected_schemas.json
└── conftest.py  # Shared fixtures
```

### Shared Fixtures (`conftest.py`)

```python
@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for test outputs"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir

@pytest.fixture
def mock_gemini_provider():
    """Mock Gemini provider with canned responses"""
    with patch('csv2pg.llm.gemini.GeminiProvider') as mock:
        mock.return_value.infer_types = AsyncMock(
            return_value=load_fixture('mock_responses/gemini_responses.json')
        )
        yield mock

@pytest.fixture
def postgres_db():
    """PostgreSQL test database"""
    # Start container, yield connection, cleanup
    pass

@pytest.fixture
def sample_csv_small(tmp_path):
    """Generate small test CSV"""
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({
        'id': range(100),
        'name': [f'Name{i}' for i in range(100)],
        'created_at': pd.date_range('2024-01-01', periods=100)
    })
    df.to_csv(csv_path, index=False)
    return csv_path
```

---

## Test Execution

### Local Development

```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit/

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_sampler.py

# Run with verbose output
uv run pytest -v

# Run performance benchmarks
uv run pytest tests/performance/ --benchmark-only
```

### Continuous Integration

**GitHub Actions Workflow:**

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v3
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: uv sync --all-extras --dev
      
      - name: Run unit tests
        run: uv run pytest tests/unit/ -v --cov=src --cov-report=xml
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-${{ matrix.python-version }}

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: csv2pg_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v3
      
      - name: Install dependencies
        run: uv sync --all-extras --dev
      
      - name: Install pgloader
        run: |
          sudo apt-get update
          sudo apt-get install -y pgloader
      
      - name: Run integration tests
        env:
          TEST_DB_URL: postgresql://test:test@localhost:5432/csv2pg_test
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY_TEST }}
        run: uv run pytest tests/integration/ -v --maxfail=1
      
      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: integration-test-artifacts
          path: |
            output/
            *.log

  lint:
    name: Code Quality
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v3
      
      - name: Install dependencies
        run: uv sync --dev
      
      - name: Run ruff
        run: uv run ruff check src/ tests/
      
      - name: Run mypy
        run: uv run mypy src/
      
      - name: Run black
        run: uv run black --check src/ tests/

  performance:
    name: Performance Benchmarks
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v3
      
      - name: Install dependencies
        run: uv sync --all-extras --dev
      
      - name: Run benchmarks
        run: uv run pytest tests/performance/ --benchmark-only --benchmark-json=benchmark.json
      
      - name: Store benchmark results
        uses: benchmark-action/github-action-benchmark@v1
        with:
          tool: 'pytest'
          output-file-path: benchmark.json
          github-token: ${{ secrets.GITHUB_TOKEN }}
          auto-push: true
```

---

## Test Data Management

### Generating Test CSVs

**Script: `tests/fixtures/generate_test_data.py`**

```python
def generate_simple_csv():
    """50 columns, 1000 rows, clear types"""
    pass

def generate_unicode_csv():
    """Test Unicode handling"""
    pass

def generate_wide_csv():
    """1000 columns"""
    pass

def generate_large_csv():
    """1M rows for performance testing"""
    pass

def generate_malformed_csv():
    """Inconsistent delimiters, encoding issues"""
    pass
```

### Fixture Validation

Before each test run, validate fixtures:
```bash
uv run python tests/fixtures/validate_fixtures.py
```

Checks:
- All fixture CSVs exist
- Checksums match (no corruption)
- Headers are valid
- Row counts are correct

---

## Test Coverage Goals

### Minimum Coverage Thresholds

```ini
# pytest.ini
[tool:pytest]
addopts = 
    --cov=src
    --cov-fail-under=90
    --cov-report=html
    --cov-report=term-missing
```

### Coverage Targets by Module

| Module | Target | Current | Priority |
|--------|--------|---------|----------|
| sampler.py | 95% | TBD | High |
| chunker.py | 95% | TBD | High |
| inference.py | 90% | TBD | High |
| llm/gemini.py | 85% | TBD | Medium |
| generator.py | 95% | TBD | High |
| state_manager.py | 95% | TBD | High |
| cli.py | 80% | TBD | Medium |
| config.py | 90% | TBD | Medium |

**Note:** Templates and utils can have lower coverage (70-80%)

---

## Quality Gates

### Pre-Commit Checks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### Pull Request Requirements

Before merging, all PRs must:
- [x] Pass all unit tests
- [x] Pass all integration tests
- [x] Pass linting (ruff, mypy, black)
- [x] Maintain or improve coverage
- [x] Include tests for new features
- [x] Update documentation

### Release Criteria

Before each release:
- [x] All tests pass on main branch
- [x] Coverage >90%
- [x] All critical bugs resolved
- [x] Performance benchmarks meet targets
- [x] Documentation is up-to-date
- [x] CHANGELOG.md updated

---

## Troubleshooting Test Failures

### Common Issues

**1. Postgres connection failures:**
```bash
# Check if container is running
docker ps | grep postgres

# Check logs
docker logs <container_id>

# Restart service
docker-compose restart postgres
```

**2. Gemini API test failures:**
```bash
# Verify mock API key is set
echo $GEMINI_API_KEY_TEST

# Check mock responses are loaded
cat tests/fixtures/mock_responses/gemini_responses.json
```

**3. CSV encoding issues:**
```python
# Debug encoding detection
from csv2pg.sampler import detect_encoding
encoding = detect_encoding("test.csv")
print(f"Detected: {encoding}")
```

**4. Flaky integration tests:**
- Add `@pytest.mark.flaky(reruns=3)` to unstable tests
- Investigate timing issues (add waits)
- Check for race conditions

---
#!/bin/bash
set -e

echo "======================================"
echo "CSV2PG AI Schema Infer - Validation"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SUCCESS=0
FAILURES=0

check_step() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}✗ $1${NC}"
        ((FAILURES++))
    fi
}

echo -e "${BLUE}1. Checking Python version...${NC}"
python3 --version | grep "Python 3.1[2-9]" > /dev/null
check_step "Python 3.12+ installed"

echo -e "\n${BLUE}2. Checking UV installation...${NC}"
uv --version > /dev/null
check_step "UV package manager installed"

echo -e "\n${BLUE}3. Installing dependencies...${NC}"
uv sync --extra dev > /dev/null 2>&1
check_step "Dependencies installed"

echo -e "\n${BLUE}4. Checking imports...${NC}"
uv run python -c "from csv2pg_ai_schema_infer import cli, config, sampler, chunker, inference, generator, state_manager, types" 2>&1
check_step "All core modules importable"

uv run python -c "from csv2pg_ai_schema_infer.llm import GeminiProvider" 2>&1
check_step "LLM modules importable"

uv run python -c "from csv2pg_ai_schema_infer.utils import logger, validation" 2>&1
check_step "Utils modules importable"

echo -e "\n${BLUE}5. Running unit tests...${NC}"
uv run pytest tests/unit/ -q --tb=short
check_step "Unit tests passing"

echo -e "\n${BLUE}6. Checking code quality...${NC}"
uv run ruff check src/ tests/ --quiet || true
check_step "Ruff linting (informational)"

echo -e "\n${BLUE}7. Testing CLI commands...${NC}"
uv run csv2pg-ai-schema-infer --help > /dev/null
check_step "Main CLI executable"

uv run csv2pg-ai-schema-infer --version > /dev/null 2>&1 || true
check_step "Version command (informational)"

echo -e "\n${BLUE}8. Creating test CSV...${NC}"
cat > /tmp/validation_test.csv << 'EOF'
id,name,email,age,created_at,active,amount
1,John Doe,john@example.com,25,2024-01-15T10:30:00,true,123.45
2,Jane Smith,jane@example.com,32,2024-01-16T14:22:00,true,456.78
3,Bob Johnson,bob@example.com,28,2024-01-17T09:15:00,false,789.01
EOF
check_step "Test CSV created"

echo -e "\n${BLUE}9. Testing validate command...${NC}"
uv run csv2pg-ai-schema-infer validate /tmp/validation_test.csv > /dev/null 2>&1
check_step "Validate command works"

echo -e "\n${BLUE}10. Testing import-csv command (dry-run, heuristic)...${NC}"
uv run csv2pg-ai-schema-infer import-csv /tmp/validation_test.csv \
    --no-llm \
    --db-url "postgresql://test:test@localhost:5432/testdb" \
    --dry-run \
    --output-dir /tmp/csv2pg_validation > /dev/null 2>&1
check_step "Import command works (dry-run)"

echo -e "\n${BLUE}11. Testing actual file generation...${NC}"
rm -rf /tmp/csv2pg_validation_real
uv run csv2pg-ai-schema-infer import-csv /tmp/validation_test.csv \
    --no-llm \
    --db-url "postgresql://test:test@localhost:5432/testdb" \
    --output-dir /tmp/csv2pg_validation_real > /dev/null 2>&1
check_step "Files generated successfully"

echo -e "\n${BLUE}12. Validating generated files...${NC}"
[ -f /tmp/csv2pg_validation_real/validation_test.load ]
check_step "pgloader config exists"

[ -f /tmp/csv2pg_validation_real/validation_test_import.sh ]
check_step "Import script exists"

[ -f /tmp/csv2pg_validation_real/validation_test_state.json ]
check_step "State file exists"

[ -x /tmp/csv2pg_validation_real/validation_test_import.sh ]
check_step "Import script is executable"

echo -e "\n${BLUE}13. Checking generated pgloader config...${NC}"
grep -q "LOAD CSV" /tmp/csv2pg_validation_real/validation_test.load
check_step "pgloader config has LOAD CSV"

grep -q "validation_test" /tmp/csv2pg_validation_real/validation_test.load
check_step "pgloader config has table name"

grep -q "CREATE TABLE" /tmp/csv2pg_validation_real/validation_test.load
check_step "pgloader config has CREATE TABLE"

echo -e "\n${BLUE}14. Checking generated import script...${NC}"
grep -q "pgloader" /tmp/csv2pg_validation_real/validation_test_import.sh
check_step "Import script calls pgloader"

grep -q "STATE_FILE" /tmp/csv2pg_validation_real/validation_test_import.sh
check_step "Import script has state management"

echo -e "\n${BLUE}15. Checking state file format...${NC}"
python3 -c "import json; json.load(open('/tmp/csv2pg_validation_real/validation_test_state.json'))" > /dev/null 2>&1
check_step "State file is valid JSON"

echo -e "\n${BLUE}16. Checking configuration files...${NC}"
[ -f config/default.yaml ]
check_step "Default config exists"

[ -f .env.template ]
check_step "Environment template exists"

echo -e "\n${BLUE}17. Checking documentation...${NC}"
[ -f README.md ] && [ -s README.md ]
check_step "README.md exists and not empty"

[ -f PLAN.md ] && [ -s PLAN.md ]
check_step "PLAN.md exists and not empty"

[ -f TESTS.md ] && [ -s TESTS.md ]
check_step "TESTS.md exists and not empty"

[ -f CHANGELOG.md ] && [ -s CHANGELOG.md ]
check_step "CHANGELOG.md exists and not empty"

echo -e "\n${BLUE}18. Checking CI/CD configuration...${NC}"
[ -f .github/workflows/ci.yml ]
check_step "CI workflow exists"

[ -f .github/workflows/release.yml ]
check_step "Release workflow exists"

[ -f .pre-commit-config.yaml ]
check_step "Pre-commit config exists"

echo -e "\n${BLUE}19. Checking project metadata...${NC}"
[ -f pyproject.toml ] && grep -q "csv2pg-ai-schema-infer" pyproject.toml
check_step "pyproject.toml configured correctly"

[ -f LICENSE ]
check_step "LICENSE file exists"

echo -e "\n${BLUE}20. Checking templates...${NC}"
[ -f src/csv2pg_ai_schema_infer/templates/pgloader.jinja2 ]
check_step "pgloader template exists"

[ -f src/csv2pg_ai_schema_infer/templates/import.sh.jinja2 ]
check_step "Import script template exists"

echo -e "\n======================================"
echo -e "${GREEN}Validation Complete!${NC}"
echo "======================================"
echo -e "Success: ${GREEN}${SUCCESS}${NC}"
echo -e "Failures: ${RED}${FAILURES}${NC}"
echo ""

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Project is ready.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Some checks failed. Review output above.${NC}"
    exit 1
fi
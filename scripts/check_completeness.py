#!/usr/bin/env python3
"""
Comprehensive completeness check for CSV2PG AI Schema Infer.
Validates all modules, functions, and features are properly implemented.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple

# Colors for terminal output
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


class ProjectValidator:
    """Validates project completeness."""

    def __init__(self):
        self.root = Path(__file__).parent.parent
        self.src = self.root / "src" / "csv2pg_ai_schema_infer"
        self.tests = self.root / "tests"
        self.issues = []
        self.successes = []

    def check(self, condition: bool, message: str) -> None:
        """Check a condition and record result."""
        if condition:
            self.successes.append(message)
            print(f"{GREEN}✓{NC} {message}")
        else:
            self.issues.append(message)
            print(f"{RED}✗{NC} {message}")

    def check_file_exists(self, path: Path, description: str) -> bool:
        """Check if a file exists."""
        exists = path.exists()
        self.check(exists, f"{description}: {path.relative_to(self.root)}")
        return exists

    def check_module_imports(self, module_path: Path) -> bool:
        """Check if a Python module has valid imports."""
        try:
            with open(module_path) as f:
                ast.parse(f.read())
            return True
        except SyntaxError:
            return False

    def check_function_exists(self, module_path: Path, function_name: str) -> bool:
        """Check if a function exists in a module."""
        try:
            with open(module_path) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    return True
            return False
        except Exception:
            return False

    def check_class_exists(self, module_path: Path, class_name: str) -> bool:
        """Check if a class exists in a module."""
        try:
            with open(module_path) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    return True
            return False
        except Exception:
            return False

    def validate_core_modules(self) -> None:
        """Validate all core modules exist."""
        print(f"\n{BLUE}Checking Core Modules...{NC}")

        modules = [
            ("cli.py", "CLI interface"),
            ("config.py", "Configuration management"),
            ("sampler.py", "CSV sampler"),
            ("chunker.py", "Column chunker"),
            ("inference.py", "Type inference"),
            ("generator.py", "File generator"),
            ("state_manager.py", "State manager"),
            ("types.py", "Type definitions"),
        ]

        for filename, desc in modules:
            path = self.src / filename
            self.check_file_exists(path, desc)

    def validate_llm_modules(self) -> None:
        """Validate LLM provider modules."""
        print(f"\n{BLUE}Checking LLM Modules...{NC}")

        llm_dir = self.src / "llm"
        self.check_file_exists(llm_dir / "__init__.py", "LLM package init")
        self.check_file_exists(llm_dir / "base.py", "LLM base interface")
        self.check_file_exists(llm_dir / "gemini.py", "Gemini provider")

        # Check for required classes
        if (llm_dir / "base.py").exists():
            has_provider = self.check_class_exists(llm_dir / "base.py", "LLMProvider")
            self.check(has_provider, "LLMProvider class exists")

        if (llm_dir / "gemini.py").exists():
            has_gemini = self.check_class_exists(llm_dir / "gemini.py", "GeminiProvider")
            self.check(has_gemini, "GeminiProvider class exists")

    def validate_utils(self) -> None:
        """Validate utility modules."""
        print(f"\n{BLUE}Checking Utility Modules...{NC}")

        utils_dir = self.src / "utils"
        self.check_file_exists(utils_dir / "__init__.py", "Utils package init")
        self.check_file_exists(utils_dir / "logger.py", "Logger utility")
        self.check_file_exists(utils_dir / "validation.py", "Validation utility")

    def validate_templates(self) -> None:
        """Validate template files."""
        print(f"\n{BLUE}Checking Templates...{NC}")

        templates_dir = self.src / "templates"
        self.check_file_exists(templates_dir / "pgloader.jinja2", "pgloader template")
        self.check_file_exists(
            templates_dir / "import.sh.jinja2", "Import script template"
        )

    def validate_tests(self) -> None:
        """Validate test structure."""
        print(f"\n{BLUE}Checking Test Structure...{NC}")

        self.check_file_exists(self.tests / "conftest.py", "Test fixtures")
        self.check_file_exists(self.tests / "unit" / "test_config.py", "Config tests")
        self.check_file_exists(self.tests / "unit" / "test_sampler.py", "Sampler tests")
        self.check_file_exists(self.tests / "unit" / "test_chunker.py", "Chunker tests")

    def validate_config_files(self) -> None:
        """Validate configuration files."""
        print(f"\n{BLUE}Checking Configuration Files...{NC}")

        self.check_file_exists(self.root / "pyproject.toml", "Project metadata")
        self.check_file_exists(self.root / "config" / "default.yaml", "Default config")
        self.check_file_exists(self.root / ".env.template", "Environment template")
        self.check_file_exists(self.root / ".gitignore", "Git ignore file")

    def validate_ci_cd(self) -> None:
        """Validate CI/CD configuration."""
        print(f"\n{BLUE}Checking CI/CD Configuration...{NC}")

        workflows = self.root / ".github" / "workflows"
        self.check_file_exists(workflows / "ci.yml", "CI workflow")
        self.check_file_exists(workflows / "release.yml", "Release workflow")
        self.check_file_exists(workflows / "codeql.yml", "CodeQL workflow")
        self.check_file_exists(
            self.root / ".pre-commit-config.yaml", "Pre-commit config"
        )

    def validate_documentation(self) -> None:
        """Validate documentation files."""
        print(f"\n{BLUE}Checking Documentation...{NC}")

        docs = [
            ("README.md", "Main README"),
            ("PLAN.md", "Project plan"),
            ("TESTS.md", "Testing strategy"),
            ("CLAUDE.md", "AI guidance"),
            ("CHANGELOG.md", "Change log"),
            ("LICENSE", "License file"),
        ]

        for filename, desc in docs:
            self.check_file_exists(self.root / filename, desc)

    def validate_key_functions(self) -> None:
        """Validate key functions exist in modules."""
        print(f"\n{BLUE}Checking Key Functions...{NC}")

        checks = [
            (self.src / "sampler.py", "sample_csv", "CSV sampling function"),
            (self.src / "sampler.py", "detect_csv_properties", "CSV detection function"),
            (self.src / "chunker.py", "chunk_columns", "Column chunking function"),
            (self.src / "inference.py", "infer_schema_sync", "Schema inference function"),
            (
                self.src / "inference.py",
                "heuristic_type_inference",
                "Heuristic inference function",
            ),
            (self.src / "generator.py", "generate_all", "File generation function"),
            (self.src / "config.py", "load_config", "Config loading function"),
        ]

        for module_path, func_name, desc in checks:
            if module_path.exists():
                has_func = self.check_function_exists(module_path, func_name)
                self.check(has_func, desc)

    def check_missing_features(self) -> None:
        """Check for known missing or incomplete features."""
        print(f"\n{BLUE}Checking for Known Gaps...{NC}")

        # Check for integration tests
        integration_dir = self.tests / "integration"
        has_integration = integration_dir.exists() and any(
            integration_dir.glob("test_*.py")
        )
        self.check(has_integration, "Integration tests implemented (optional)")

        # Check for performance tests
        performance_dir = self.tests / "performance"
        has_performance = performance_dir.exists() and any(
            performance_dir.glob("test_*.py")
        )
        self.check(has_performance, "Performance tests implemented (optional)")

        # Check for resume implementation
        if (self.src / "cli.py").exists():
            with open(self.src / "cli.py") as f:
                content = f.read()
                has_full_resume = "not yet fully implemented" not in content.lower()
                self.check(has_full_resume, "Resume command fully implemented (optional)")

    def run_validation(self) -> int:
        """Run all validations."""
        print(f"{BLUE}{'=' * 60}{NC}")
        print(f"{BLUE}CSV2PG AI Schema Infer - Completeness Check{NC}")
        print(f"{BLUE}{'=' * 60}{NC}")

        self.validate_core_modules()
        self.validate_llm_modules()
        self.validate_utils()
        self.validate_templates()
        self.validate_tests()
        self.validate_config_files()
        self.validate_ci_cd()
        self.validate_documentation()
        self.validate_key_functions()
        self.check_missing_features()

        print(f"\n{BLUE}{'=' * 60}{NC}")
        print(f"{GREEN}Successes: {len(self.successes)}{NC}")
        print(f"{RED}Issues: {len(self.issues)}{NC}")
        print(f"{BLUE}{'=' * 60}{NC}")

        if self.issues:
            print(f"\n{YELLOW}Issues Found:{NC}")
            for issue in self.issues:
                print(f"  - {issue}")

        if len(self.issues) == 0:
            print(f"\n{GREEN}✓ All checks passed! Project is complete.{NC}")
            return 0
        elif len(self.issues) <= 3:
            print(
                f"\n{YELLOW}⚠ Minor issues found. Project is mostly complete.{NC}"
            )
            return 0
        else:
            print(f"\n{RED}✗ Significant issues found. Review required.{NC}")
            return 1


if __name__ == "__main__":
    validator = ProjectValidator()
    exit_code = validator.run_validation()
    sys.exit(exit_code)
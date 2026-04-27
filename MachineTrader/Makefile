# Makefile for MachineTrader Package
# Trading System Package for Alpaca API Integration
# Author: AI Assistant
# Usage: make [target]

# Configuration
PACKAGE_NAME = MachineTrader
PYTHON = python3
PIP = pip3
VENV_DIR = .venv
VENV_PYTHON = $(VENV_DIR)/bin/python
VENV_PIP = $(VENV_DIR)/bin/pip
SOURCE_DIR = .
TEST_DIR = tests
BUILD_DIR = build
DIST_DIR = dist

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

# Default target
.PHONY: help
help:
	@echo "$(GREEN)MachineTrader Package Build System$(NC)"
	@echo "====================================="
	@echo ""
	@echo "$(YELLOW)Available targets:$(NC)"
	@echo "  help          - Show this help message"
	@echo "  install       - Install package and dependencies"
	@echo "  install-dev   - Install package with development dependencies"
	@echo "  venv          - Create virtual environment"
	@echo "  requirements  - Generate requirements.txt from current environment"
	@echo "  deps          - Install dependencies from requirements.txt"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  lint          - Run code linting (flake8, pylint)"
	@echo "  format        - Format code with black and isort"
	@echo "  format-check  - Check code formatting without making changes"
	@echo "  type-check    - Run type checking with mypy"
	@echo "  build         - Build package distributions"
	@echo "  clean         - Clean build artifacts and cache files"
	@echo "  clean-all     - Clean everything including virtual environment"
	@echo "  docs          - Generate documentation"
	@echo "  serve-docs    - Serve documentation locally"
	@echo "  security      - Run security checks (bandit, safety)"
	@echo "  coverage      - Run tests with coverage report"
	@echo "  profile       - Profile package performance"
	@echo "  validate      - Run all validation checks"
	@echo "  package-info  - Show package information"
	@echo ""

# Virtual Environment Management
.PHONY: venv
venv:
	@echo "$(GREEN)Creating virtual environment...$(NC)"
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PIP) install --upgrade pip setuptools wheel
	@echo "$(GREEN)Virtual environment created. Activate with: source $(VENV_DIR)/bin/activate$(NC)"

# Dependency Management
.PHONY: requirements
requirements:
	@echo "$(GREEN)Generating requirements.txt...$(NC)"
	@echo "# MachineTrader Package Dependencies" > requirements.txt
	@echo "# Generated on $$(date)" >> requirements.txt
	@echo "" >> requirements.txt
	@echo "# Core dependencies" >> requirements.txt
	@echo "pandas>=1.5.0" >> requirements.txt
	@echo "numpy>=1.21.0" >> requirements.txt
	@echo "websockets>=10.0" >> requirements.txt
	@echo "python-dotenv>=0.19.0" >> requirements.txt
	@echo "alpaca-py>=0.8.0" >> requirements.txt
	@echo "matplotlib>=3.5.0" >> requirements.txt
	@echo "requests>=2.28.0" >> requirements.txt
	@echo "" >> requirements.txt
	@echo "# Development dependencies (install with make install-dev)" >> requirements.txt
	@echo "pytest>=7.0.0" >> requirements.txt
	@echo "pytest-cov>=4.0.0" >> requirements.txt
	@echo "pytest-asyncio>=0.21.0" >> requirements.txt
	@echo "black>=22.0.0" >> requirements.txt
	@echo "isort>=5.10.0" >> requirements.txt
	@echo "flake8>=5.0.0" >> requirements.txt
	@echo "pylint>=2.15.0" >> requirements.txt
	@echo "mypy>=0.991" >> requirements.txt
	@echo "bandit>=1.7.0" >> requirements.txt
	@echo "safety>=2.3.0" >> requirements.txt
	@echo "sphinx>=5.0.0" >> requirements.txt
	@echo "sphinx-rtd-theme>=1.2.0" >> requirements.txt
	@echo "$(GREEN)Requirements file generated!$(NC)"

.PHONY: deps
deps:
	@echo "$(GREEN)Installing dependencies...$(NC)"
	$(PIP) install -r requirements.txt

.PHONY: install
install: requirements
	@echo "$(GREEN)Installing MachineTrader package...$(NC)"
	$(PIP) install -e .
	$(PIP) install pandas numpy websockets python-dotenv alpaca-py matplotlib requests
	@echo "$(GREEN)Package installed successfully!$(NC)"

.PHONY: install-dev
install-dev: requirements
	@echo "$(GREEN)Installing MachineTrader package with development dependencies...$(NC)"
	$(PIP) install -e .
	$(PIP) install pandas numpy websockets python-dotenv alpaca-py matplotlib requests
	$(PIP) install pytest pytest-cov pytest-asyncio black isort flake8 pylint mypy bandit safety sphinx sphinx-rtd-theme
	@echo "$(GREEN)Development environment installed successfully!$(NC)"

# Setup.py creation
.PHONY: setup-py
setup-py:
	@echo "$(GREEN)Creating setup.py...$(NC)"
	@cat > setup.py << 'EOF'
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="MachineTrader",
    version="1.0.0",
    author="Trading System Developer",
    author_email="dev@machinetrader.com",
    description="Advanced algorithmic trading system for Alpaca API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/MachineTrader",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pandas>=1.5.0",
        "numpy>=1.21.0",
        "websockets>=10.0",
        "python-dotenv>=0.19.0",
        "alpaca-py>=0.8.0",
        "matplotlib>=3.5.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "isort>=5.10.0",
            "flake8>=5.0.0",
            "pylint>=2.15.0",
            "mypy>=0.991",
            "bandit>=1.7.0",
            "safety>=2.3.0",
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "machinetrader=MachineTrader.trading:main",
        ],
    },
)
EOF
	@echo "$(GREEN)setup.py created!$(NC)"

# Testing
.PHONY: test-dir
test-dir:
	@if [ ! -d "$(TEST_DIR)" ]; then \
		echo "$(GREEN)Creating test directory structure...$(NC)"; \
		mkdir -p $(TEST_DIR); \
		touch $(TEST_DIR)/__init__.py; \
		echo "import unittest\nfrom MachineTrader import GetArgs, CreateStrategy, Bar\n\nclass TestMachineTrader(unittest.TestCase):\n    def test_get_args_init(self):\n        args = GetArgs()\n        self.assertIsNotNone(args)\n\n    def test_create_strategy_init(self):\n        strategy = CreateStrategy()\n        self.assertIsNotNone(strategy)\n\n    def test_bar_init(self):\n        bar = Bar()\n        self.assertIsNotNone(bar)\n\nif __name__ == '__main__':\n    unittest.main()" > $(TEST_DIR)/test_basic.py; \
		echo "$(GREEN)Basic test structure created!$(NC)"; \
	fi

.PHONY: test
test: test-dir
	@echo "$(GREEN)Running all tests...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) -v --tb=short

.PHONY: test-unit
test-unit: test-dir
	@echo "$(GREEN)Running unit tests...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) -v -k "unit" --tb=short

.PHONY: test-integration
test-integration: test-dir
	@echo "$(GREEN)Running integration tests...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) -v -k "integration" --tb=short

.PHONY: coverage
coverage: test-dir
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(PYTHON) -m pytest $(TEST_DIR) --cov=MachineTrader --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)Coverage report generated in htmlcov/$(NC)"

# Code Quality
.PHONY: lint
lint:
	@echo "$(GREEN)Running code linting...$(NC)"
	@echo "$(YELLOW)Running flake8...$(NC)"
	-$(PYTHON) -m flake8 MachineTrader --count --select=E9,F63,F7,F82 --show-source --statistics
	@echo "$(YELLOW)Running pylint...$(NC)"
	-$(PYTHON) -m pylint MachineTrader --output-format=colorized

.PHONY: format
format:
	@echo "$(GREEN)Formatting code...$(NC)"
	$(PYTHON) -m black MachineTrader AlpacaSDK TechIndic *.py
	$(PYTHON) -m isort MachineTrader AlpacaSDK TechIndic *.py

.PHONY: format-check
format-check:
	@echo "$(GREEN)Checking code formatting...$(NC)"
	$(PYTHON) -m black --check MachineTrader AlpacaSDK TechIndic *.py
	$(PYTHON) -m isort --check-only MachineTrader AlpacaSDK TechIndic *.py

.PHONY: type-check
type-check:
	@echo "$(GREEN)Running type checking...$(NC)"
	$(PYTHON) -m mypy MachineTrader --ignore-missing-imports

.PHONY: security
security:
	@echo "$(GREEN)Running security checks...$(NC)"
	@echo "$(YELLOW)Running bandit...$(NC)"
	-$(PYTHON) -m bandit -r MachineTrader
	@echo "$(YELLOW)Running safety...$(NC)"
	-$(PYTHON) -m safety check

# Build and Distribution
.PHONY: build
build: clean setup-py
	@echo "$(GREEN)Building package distributions...$(NC)"
	$(PYTHON) setup.py sdist bdist_wheel
	@echo "$(GREEN)Build complete! Files in $(DIST_DIR)/$(NC)"

.PHONY: check-dist
check-dist: build
	@echo "$(GREEN)Checking distribution...$(NC)"
	$(PYTHON) -m twine check $(DIST_DIR)/*

# Documentation
.PHONY: docs
docs:
	@echo "$(GREEN)Generating documentation...$(NC)"
	@if [ ! -d "docs" ]; then mkdir docs; fi
	@echo "$(YELLOW)Creating Sphinx configuration...$(NC)"
	@cat > docs/conf.py << 'EOF'
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'MachineTrader'
copyright = '2024, MachineTrader Development Team'
author = 'MachineTrader Development Team'
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
EOF
	@echo "$(YELLOW)Creating main documentation file...$(NC)"
	@cat > docs/index.rst << 'EOF'
MachineTrader Documentation
==========================

Welcome to MachineTrader's documentation!

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
EOF
	@cd docs && $(PYTHON) -m sphinx.ext.apidoc -o . ../MachineTrader
	@cd docs && make html
	@echo "$(GREEN)Documentation generated in docs/_build/html/$(NC)"

.PHONY: serve-docs
serve-docs:
	@echo "$(GREEN)Serving documentation at http://localhost:8000$(NC)"
	@cd docs/_build/html && $(PYTHON) -m http.server 8000

# Performance and Profiling
.PHONY: profile
profile:
	@echo "$(GREEN)Running performance profiling...$(NC)"
	$(PYTHON) -m cProfile -o profile_output.prof -c "from MachineTrader import GetArgs; args = GetArgs(); args.parse_arguments()"
	@echo "$(GREEN)Profile saved to profile_output.prof$(NC)"
	@echo "$(YELLOW)View with: python -m pstats profile_output.prof$(NC)"

# Validation and Quality Assurance
.PHONY: validate
validate: format-check lint type-check security test
	@echo "$(GREEN)All validation checks completed!$(NC)"

# Package Information
.PHONY: package-info
package-info:
	@echo "$(GREEN)MachineTrader Package Information$(NC)"
	@echo "=================================="
	@echo "Package Name: $(PACKAGE_NAME)"
	@echo "Version: 1.0.0"
	@echo "Python Version: $$($(PYTHON) --version)"
	@echo "Virtual Environment: $(if $(VIRTUAL_ENV),Active ($(VIRTUAL_ENV)),Not active)"
	@echo ""
	@echo "$(YELLOW)Package Structure:$(NC)"
	@find MachineTrader -name "*.py" | head -10
	@echo ""
	@echo "$(YELLOW)Dependencies Status:$(NC)"
	@$(PIP) show pandas numpy websockets python-dotenv 2>/dev/null | grep "Version" || echo "Some dependencies not installed"

# Environment Management
.PHONY: env-info
env-info:
	@echo "$(GREEN)Environment Information$(NC)"
	@echo "========================"
	@echo "Python: $$(which $(PYTHON))"
	@echo "Pip: $$(which $(PIP))"
	@echo "Virtual Environment: $(if $(VIRTUAL_ENV),$(VIRTUAL_ENV),None)"
	@echo "Working Directory: $$(pwd)"
	@echo "Git Status: $$(git status --porcelain | wc -l) modified files"

# Cleanup
.PHONY: clean
clean:
	@echo "$(GREEN)Cleaning build artifacts...$(NC)"
	rm -rf $(BUILD_DIR)
	rm -rf $(DIST_DIR)
	rm -rf *.egg-info
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf profile_output.prof
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "$(GREEN)Clean complete!$(NC)"

.PHONY: clean-all
clean-all: clean
	@echo "$(GREEN)Cleaning everything including virtual environment...$(NC)"
	rm -rf $(VENV_DIR)
	rm -rf .mypy_cache
	rm -rf docs/_build
	@echo "$(GREEN)Deep clean complete!$(NC)"

# Quick Development Targets
.PHONY: quick-test
quick-test:
	@echo "$(GREEN)Quick test run...$(NC)"
	$(PYTHON) -c "from MachineTrader import GetArgs, CreateStrategy, Bar; print('✓ MachineTrader imports working')"
	$(PYTHON) -c "from AlpacaSDK import AlpacaSDK; print('✓ AlpacaSDK imports working')"
	$(PYTHON) -c "from TechIndic import MovAvg, Risk; print('✓ TechIndic imports working')"

.PHONY: dev-setup
dev-setup: venv install-dev
	@echo "$(GREEN)Development environment setup complete!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "1. Activate virtual environment: source $(VENV_DIR)/bin/activate"
	@echo "2. Run tests: make test"
	@echo "3. Check code quality: make validate"

# CI/CD Support
.PHONY: ci
ci: install-dev validate coverage build
	@echo "$(GREEN)CI pipeline completed successfully!$(NC)"

# Example usage target
.PHONY: example
example:
	@echo "$(GREEN)Running MachineTrader example...$(NC)"
	$(PYTHON) -c "from MachineTrader import GetArgs; args = GetArgs(); parsed = args.parse_arguments(['--symbol', 'AAPL', '--quantity', '100']); print('Parsed arguments:', parsed)"

# Check if all required files exist
.PHONY: check-structure
check-structure:
	@echo "$(GREEN)Checking package structure...$(NC)"
	@for file in MachineTrader/__init__.py MachineTrader/trading.py AlpacaSDK/__init__.py TechIndic/__init__.py utils.py; do \
		if [ -f "$$file" ]; then \
			echo "✓ $$file"; \
		else \
			echo "$(RED)✗ $$file missing$(NC)"; \
		fi; \
	done

# Default target when no target is specified
.DEFAULT_GOAL := help

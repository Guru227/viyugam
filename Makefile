.PHONY: install-dev install-hooks lint typecheck security deps complexity docs deadcode coverage funcmetrics hotspots report badges quality test-quality mutation

SRC     = viyugam
REPORTS = reports

# Resolve tools from the virtualenv if present, otherwise fall back to PATH.
VENV        := $(shell [ -d .venv ] && echo .venv || echo "")
_bin         = $(if $(VENV),$(VENV)/bin/,)
RUFF        := $(_bin)ruff
MYPY        := $(_bin)mypy
BANDIT      := $(_bin)bandit
PIP_AUDIT   := $(_bin)pip-audit
RADON       := $(_bin)radon
INTERROGATE := $(_bin)interrogate
VULTURE     := $(_bin)vulture
PYTEST      := $(_bin)pytest
LIZARD      := $(_bin)lizard
PYTHON      := $(_bin)python3

install-dev:
	uv add --dev ruff mypy bandit pip-audit radon interrogate vulture anybadge pytest-cov lizard

install-hooks:
	cp scripts/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed."

lint:
	mkdir -p $(REPORTS)
	$(RUFF) check $(SRC) --output-format=json > $(REPORTS)/ruff.json 2>/dev/null || true
	$(RUFF) check $(SRC) || true

typecheck:
	mkdir -p $(REPORTS)
	$(MYPY) $(SRC) --ignore-missing-imports 2>&1 | tee $(REPORTS)/mypy.txt; true

security:
	mkdir -p $(REPORTS)
	$(BANDIT) -r $(SRC) -ll -f json -o $(REPORTS)/bandit.json 2>/dev/null || true
	$(BANDIT) -r $(SRC) -ll -q || true

deps:
	mkdir -p $(REPORTS)
	$(PIP_AUDIT) --ignore-vuln PYSEC-2022-42969 -f json -o $(REPORTS)/pip-audit.json 2>/dev/null || true
	$(PIP_AUDIT) --ignore-vuln PYSEC-2022-42969 || true

complexity:
	mkdir -p $(REPORTS)
	$(RADON) cc $(SRC) --json > $(REPORTS)/complexity.json
	$(RADON) raw $(SRC) -s > $(REPORTS)/raw-metrics.txt
	@echo "=== Cyclomatic Complexity (C+ flagged) ==="
	$(RADON) cc $(SRC) -a -s --min C || true
	@echo "=== Maintainability Index ==="
	$(RADON) mi $(SRC) -s || true

docs:
	mkdir -p $(REPORTS)
	$(INTERROGATE) $(SRC) --output $(REPORTS)/interrogate.txt -v || true
	$(INTERROGATE) $(SRC) || true

deadcode:
	mkdir -p $(REPORTS)
	$(VULTURE) $(SRC) vulture_whitelist.py --min-confidence 80 > $(REPORTS)/vulture.txt 2>&1 || true
	$(VULTURE) $(SRC) vulture_whitelist.py --min-confidence 80 || true

coverage:
	mkdir -p $(REPORTS)
	$(PYTEST) tests/ \
		--cov=$(SRC) \
		--cov-report=json:$(REPORTS)/coverage.json \
		-q --tb=no 2>&1 | tee $(REPORTS)/coverage.txt; true

funcmetrics:
	mkdir -p $(REPORTS)
	$(LIZARD) $(SRC) -l python --csv > $(REPORTS)/lizard.csv 2>/dev/null || true
	@echo "=== Functions exceeding 50 lines or CCN > 10 ==="
	$(LIZARD) $(SRC) -l python --CCN 10 --length 50 -w || true

hotspots:
	@echo "=== Top 10 Largest Files (SLOC) ==="
	$(PYTHON) scripts/hotspots.py
	@echo ""
	@echo "=== Bottom 10 Files by Maintainability Index (grade C or below) ==="
	$(RADON) mi $(SRC) --min C -s 2>/dev/null | head -20 || true

test-quality:
	mkdir -p $(REPORTS)
	$(PYTHON) scripts/test_quality.py

mutation:
	mkdir -p $(REPORTS)
	$(PYTHON) scripts/mutation_test.py --max-mutants 80
	$(PYTHON) scripts/test_quality.py

report: lint typecheck security deps complexity docs deadcode coverage funcmetrics test-quality
	@echo ""
	@echo "=== All reports in $(REPORTS)/ ==="

badges:
	mkdir -p badges
	$(PYTHON) scripts/gen_badges.py

quality: report badges
	@echo ""
	@echo "=== Quality check complete. badges/ updated. ==="

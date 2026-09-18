PYTHON ?= python3
PROJECT := projects/laundrybench

.PHONY: install check test demo lint

install:
	cd $(PROJECT) && $(PYTHON) -m pip install -e ".[dev]"

# Full gate. This is exactly what CI runs; keep the two in sync.
check:
	@set -e; failed=""; \
	$(MAKE) --no-print-directory lint || failed="$$failed lint"; \
	$(MAKE) --no-print-directory test || failed="$$failed test"; \
	if [ -n "$$failed" ]; then echo "GATE FAIL —$$failed"; exit 1; fi; \
	echo "GATE PASS — lint and tests green."

test:
	cd $(PROJECT) && $(PYTHON) -m pytest

demo:
	cd $(PROJECT) && $(PYTHON) scripts/evaluate.py --episodes 10

lint:
	cd $(PROJECT) && $(PYTHON) -m ruff check .

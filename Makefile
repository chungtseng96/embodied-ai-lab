PYTHON ?= python3
# A PYTHON containing a slash is resolved to an absolute path before the `cd`, so
# `PYTHON=projects/laundrybench/.venv/bin/python make check` works from the repo root.
PYTHON_CMD := $(if $(findstring /,$(PYTHON)),$(abspath $(PYTHON)),$(PYTHON))
PROJECT := projects/laundrybench

.PHONY: install check lint test smoke demo lerobot-check host-check

install:
	cd $(PROJECT) && $(PYTHON_CMD) -m pip install -e ".[dev]"

# Full gate. This is exactly what CI runs; keep the two in sync.
check:
	@set -e; failed=""; \
	$(MAKE) --no-print-directory lint || failed="$$failed lint"; \
	$(MAKE) --no-print-directory test || failed="$$failed test"; \
	$(MAKE) --no-print-directory smoke || failed="$$failed smoke"; \
	if [ -n "$$failed" ]; then echo "GATE FAIL —$$failed"; exit 1; fi; \
	echo "GATE PASS — lint, tests, and script smoke green."

lint:
	cd $(PROJECT) && $(PYTHON_CMD) -m ruff check .

test:
	cd $(PROJECT) && $(PYTHON_CMD) -m pytest

# Scripts compile and the host check runs. Needs no LeRobot, so it is safe in CI.
smoke:
	cd $(PROJECT) && $(PYTHON_CMD) -m compileall -q scripts
	cd $(PROJECT) && $(PYTHON_CMD) scripts/check_host_setup.py >/dev/null

demo:
	cd $(PROJECT) && $(PYTHON_CMD) scripts/evaluate.py --episodes 10

# Not part of `check`: exits non-zero without a LeRobot environment.
lerobot-check:
	cd $(PROJECT) && $(PYTHON_CMD) scripts/check_lerobot.py

host-check:
	$(PYTHON_CMD) $(PROJECT)/scripts/check_host_setup.py

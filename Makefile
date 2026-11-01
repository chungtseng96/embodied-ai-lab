PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHON_CMD := $(if $(findstring /,$(PYTHON)),$(abspath $(PYTHON)),$(PYTHON))
PROJECT := projects/laundrybench

.PHONY: install test demo lint check smoke lerobot-check host-check

install:
	cd $(PROJECT) && $(PYTHON_CMD) -m pip install -e ".[dev]"

test:
	cd $(PROJECT) && $(PYTHON_CMD) -m pytest

demo:
	cd $(PROJECT) && $(PYTHON_CMD) scripts/evaluate.py --episodes 10 --experiment exp-000-mock-smoke --force

lint:
	cd $(PROJECT) && $(PYTHON_CMD) -m ruff check .

check: test lint smoke

smoke:
	$(PYTHON_CMD) -m compileall -q $(PROJECT)/scripts
	$(PYTHON_CMD) $(PROJECT)/scripts/check_host_setup.py

lerobot-check:
	cd $(PROJECT) && $(PYTHON_CMD) scripts/check_lerobot.py

host-check:
	$(PYTHON_CMD) $(PROJECT)/scripts/check_host_setup.py

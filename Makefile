PYTHON ?= python3
PYTHON_CMD := $(if $(findstring /,$(PYTHON)),$(abspath $(PYTHON)),$(PYTHON))
PROJECT := projects/laundrybench

.PHONY: install test demo lint check lerobot-check host-check

install:
	cd $(PROJECT) && $(PYTHON_CMD) -m pip install -e ".[dev]"

test:
	cd $(PROJECT) && $(PYTHON_CMD) -m pytest

demo:
	cd $(PROJECT) && $(PYTHON_CMD) scripts/evaluate.py --episodes 10

lint:
	cd $(PROJECT) && $(PYTHON_CMD) -m ruff check .

check: test lint

lerobot-check:
	cd $(PROJECT) && $(PYTHON_CMD) scripts/check_lerobot.py

host-check:
	$(PYTHON_CMD) $(PROJECT)/scripts/check_host_setup.py

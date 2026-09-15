PYTHON ?= python3
PROJECT := projects/laundrybench

.PHONY: install test demo lint

install:
	cd $(PROJECT) && $(PYTHON) -m pip install -e ".[dev]"

test:
	cd $(PROJECT) && $(PYTHON) -m pytest

demo:
	cd $(PROJECT) && $(PYTHON) scripts/evaluate.py --episodes 10

lint:
	cd $(PROJECT) && $(PYTHON) -m ruff check .

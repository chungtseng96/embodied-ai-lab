PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHON_CMD := $(if $(findstring /,$(PYTHON)),$(abspath $(PYTHON)),$(PYTHON))
PROJECT := projects/laundrybench

.PHONY: install test demo lint check smoke factory-test factory-dispatch lerobot-check host-check frontend-install frontend-check web-demo web

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

# Factory scripts at the repository root: lint with the project's Ruff config, then their tests.
factory-test:
	$(PYTHON_CMD) -m ruff check --config $(PROJECT)/pyproject.toml scripts
	$(PYTHON_CMD) -m pytest -q scripts

# Start one factory run on the oldest factory:ready ticket (see docs/agents/factory.md).
factory-dispatch:
	$(PYTHON_CMD) scripts/factory_dispatch.py run

lerobot-check:
	cd $(PROJECT) && $(PYTHON_CMD) scripts/check_lerobot.py

host-check:
	$(PYTHON_CMD) $(PROJECT)/scripts/check_host_setup.py

frontend-install:
	npm ci --prefix $(PROJECT)/frontend

frontend-check:
	npm test --prefix $(PROJECT)/frontend
	npm run build --prefix $(PROJECT)/frontend

web-demo:
	$(PYTHON_CMD) $(PROJECT)/scripts/demo_web.py --output-dir $(PROJECT)/outputs

web:
	$(PYTHON_CMD) $(PROJECT)/scripts/serve.py --outputs-root $(PROJECT)/outputs --frontend-dir $(PROJECT)/frontend/dist

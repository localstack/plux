VENV_BIN = python3 -m venv
VENV_DIR ?= .venv

VENV_ACTIVATE = . $(VENV_DIR)/bin/activate


venv: $(VENV_DIR)/bin/activate

$(VENV_DIR)/bin/activate: pyproject.toml
	test -d $(VENV_DIR) || $(VENV_BIN) $(VENV_DIR)
	$(VENV_ACTIVATE); pip install -e ".[dev]"
	touch $(VENV_DIR)/bin/activate

$(VENV_DIR)/.docs-install: pyproject.toml $(VENV_DIR)/bin/activate
	$(VENV_ACTIVATE); pip install -e .[docs]
	touch $(VENV_DIR)/.docs-install

install-docs: $(VENV_DIR)/.docs-install

docs: install-docs
	$(VENV_ACTIVATE); cd docs && make html

clean:
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/
	rm -rf .venv

clean-dist: clean
	rm -rf dist/

lint: venv
	$(VENV_ACTIVATE); python -m ruff check . && python -m mypy

format: venv
	$(VENV_ACTIVATE); python -m ruff format . && python -m ruff check . --fix

test: venv
	$(VENV_ACTIVATE); python -m pytest

dist: venv
	$(VENV_ACTIVATE); python -m build

install: venv
	$(VENV_ACTIVATE); pip install -e .

upload: venv test dist
	$(VENV_ACTIVATE); pip install --upgrade twine; twine upload dist/*

.PHONY: clean clean-dist format

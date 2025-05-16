PYTHON ?= python
PIP ?= pip

VENV_DIR ?=
CONDA_ENV ?=

ifdef VENV_DIR
    # Virtual environment activation
    ifeq ($(OS),Windows_NT)
        ACTIVATE_CMD := . $(VENV_DIR)/Scripts/activate
    else
        ACTIVATE_CMD := . $(VENV_DIR)/bin/activate
    endif
else ifdef CONDA_ENV
    CONDA ?= conda
    ACTIVATE_CMD := . $$($(CONDA) info --base)/etc/profile.d/conda.sh && $(CONDA) activate $(CONDA_ENV)
else
    ACTIVATE_CMD := :
endif

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

install-deps:
	$(ACTIVATE_CMD) && \
	$(PIP) install -r requirements/dev.txt && \
	$(PIP) install -r requirements/app.txt

install:
	$(ACTIVATE_CMD) && \
	$(PIP) install --editable .

pre-commit:
	$(ACTIVATE_CMD) && \
	pre-commit run --all-files

test: pre-commit
	$(ACTIVATE_CMD) && \
	$(PYTHON) -m pytest -v --cov=pymortem --cov-report=term-missing --cov-report=xml:coverage.xml && \
	coverage-badge -f -o coverage.svg

build: clean
	$(ACTIVATE_CMD) && \
	$(PIP) install wheel && \
	$(PYTHON) setup.py sdist bdist_wheel

check-dist: build
	$(ACTIVATE_CMD) && \
	$(PIP) install twine && \
	$(PYTHON) -m twine check dist/*

publish-test: check-dist
	$(ACTIVATE_CMD) && \
	$(PYTHON) -m twine upload --verbose --repository-url https://test.pypi.org/legacy/ dist/*

publish: check-dist
	$(ACTIVATE_CMD) && \
	$(PYTHON) -m twine upload dist/*

.PHONY: clean install-deps install pre-commit test build lint format check-dist publish-test publish

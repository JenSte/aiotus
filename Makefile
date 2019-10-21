all: flake8-check isort-check mypy-check

black:
	black aiotus scripts/aiotus-client tests

flake8-check:
	@echo Running flake8...
	@flake8 \
	    aiotus scripts/* tests

isort-check:
	@echo Running isort...
	@isort \
	    --recursive \
	    aiotus scripts/* tests

mypy-check:
	@echo Running mypy...
	@mypy \
	    --strict \
	    aiotus scripts/*
	@mypy \
	    tests

test .coverage:
	pytest --cov=aiotus tests

coverage_html/index.html: .coverage
	coverage html -d coverage_html

venv:
	python3 -m venv venv
	source venv/bin/activate; \
	    pip3 install -r requirements_dev.txt; \
	    pip3 install -e .

clean:
	@rm -f \
	    .coverage
	@rm -rf \
	    .mypy_cache \
	    .pytest_cache \
	    aiotus.egg-info \
	    build \
	    coverage_html \
	    dist \
	    venv

.PHONY: \
	black \
	clean \
	flake8-check \
	isort-check \
	mypy-check \
	test

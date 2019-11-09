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

test .coverage: tusd
	pytest --cov=aiotus tests

coverage_html/index.html: .coverage
	coverage html -d coverage_html

venv:
	python3 -m venv venv
	source venv/bin/activate; \
	    pip3 install -r requirements_dev.txt; \
	    pip3 install -e .

TUSD_VERSION = v1.0.2
TUSD_ARCH = amd64
TUSD_ARCHIVE = tusd_linux_${TUSD_ARCH}.tar.gz

${TUSD_ARCHIVE}:
	wget --quiet https://github.com/tus/tusd/releases/download/${TUSD_VERSION}/tusd_linux_${TUSD_ARCH}.tar.gz

tusd: ${TUSD_ARCHIVE}
	tar -xf ${TUSD_ARCHIVE} --strip-components 1 tusd_linux_${TUSD_ARCH}/tusd
	touch $@


clean:
	@rm -f \
	    .coverage
	@rm -rf \
	    .mypy_cache \
	    .pytest_cache \
	    .xprocess \
	    aiotus.egg-info \
	    build \
	    coverage_html \
	    dist

veryclean: clean
	@rm -f \
	    tusd \
	    ${TUSD_ARCHIVE}
	@rm -rf \
	    venv

.PHONY: \
	black \
	clean \
	flake8-check \
	isort-check \
	mypy-check \
	test

all: black-check flake8-check isort-check mypy-check bandit-check test

bandit-check:
	@echo Running bandit...
	@bandit\
	    --silent \
	    --recursive \
	    aiotus

black:
	@echo Formatting code using black...
	@black aiotus tests

black-check:
	@echo Running black...
	@black \
	    --check \
	    --diff \
	    aiotus tests setup.py

flake8-check:
	@echo Running flake8...
	@flake8 \
	    aiotus tests setup.py

isort-check:
	@echo Running isort...
	@isort \
	    --check-only \
	    --diff \
	    aiotus tests setup.py

mypy-check:
	@echo Running mypy...
	@mypy \
	    --strict \
	    aiotus
	@mypy \
	    tests

test .coverage: tusd tests/nginx.key tests/selfsigned.crt
	pytest --cov=aiotus tests

coverage_html/index.html: .coverage
	@coverage html -d coverage_html
	@echo Coverage report ready at $$(realpath $@)

doc:
	make -C docs clean html

venv:
	python3 -m venv venv
	source venv/bin/activate; \
	    pip3 install --upgrade pip; \
	    pip3 install -r requirements_dev.txt; \
	    pip3 install -e .

TUSD_VERSION = v1.4.0
TUSD_ARCH = amd64
TUSD_ARCHIVE = tusd_linux_${TUSD_ARCH}.tar.gz

${TUSD_ARCHIVE}:
	wget --quiet https://github.com/tus/tusd/releases/download/${TUSD_VERSION}/tusd_linux_${TUSD_ARCH}.tar.gz

tusd: ${TUSD_ARCHIVE}
	tar -xf ${TUSD_ARCHIVE} --strip-components 1 tusd_linux_${TUSD_ARCH}/tusd
	touch $@

tests/nginx.key tests/selfsigned.crt:
	openssl req \
	    -new -x509 -nodes\
	    -days 3650 \
	    -subj '/CN=localhost' \
	    -keyout tests/nginx.key \
	    -out tests/selfsigned.crt

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
	    ${TUSD_ARCHIVE} \
	    tests/nginx.key \
	    tests/selfsigned.crt
	@rm -rf \
	    venv

.PHONY: \
	black \
	clean \
	doc \
	flake8-check \
	isort-check \
	mypy-check \
	test \
	veryclean

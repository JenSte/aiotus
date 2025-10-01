all: \
	black-check \
	flake8-check \
	isort-check \
	lint \
	mypy-check \
	bandit-check \
	zizmor-check \
	test

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
	    aiotus tests

flake8-check:
	@echo Running flake8...
	@flake8 \
	    aiotus tests

isort-check:
	@echo Running isort...
	@isort \
	    --check-only \
	    --diff \
	    aiotus tests

lint:
	@echo Running pycodestyle...
	@pycodestyle --config=.pycodestyle.ini aiotus tests
	@echo Running pydoclint...
	@pydoclint aiotus

mypy-check:
	@echo Running mypy...
	@mypy \
	    --strict \
	    aiotus tests

zizmor-check:
	@echo Running zizmor...
	zizmor .github/workflows

test .coverage: tusd tests/nginx.key tests/selfsigned.crt
	pytest --cov=aiotus tests

coverage_html/index.html: .coverage
	@coverage html -d coverage_html
	@echo Coverage report ready at $$(realpath $@)

pyupgrade:
	@echo Running pyupgrade...
	pyupgrade \
	    --py39-plus \
	    --keep-runtime-typing \
	    aiotus/*.py

doc:
	make -C docs clean html

tox:
	unset PYTHONPATH && \
	    export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring && \
	    tox
	coverage combine .coverage.*

venv:
	python3 -m venv venv
	. venv/bin/activate; \
	    pip3 install --upgrade pip; \
	    pip3 install -r requirements.txt; \
	    pip3 install -e .

TUSD_VERSION = v2.8.0
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
	    -subj '/' \
	    -addext 'subjectAltName = DNS:localhost' \
	    -keyout tests/nginx.key \
	    -out tests/selfsigned.crt

show-certificate: tests/selfsigned.crt
	@openssl x509 \
	    -text \
	    -in $< \
	    -noout

clean:
	@rm -f \
	    .coverage*
	@rm -rf \
	    .mypy_cache \
	    .pytest_cache \
	    .tox \
	    .xprocess \
	    aiotus.egg-info \
	    build \
	    coverage_html \
	    dist \
	    docs/build

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
	pyupgrade \
	doc \
	flake8-check \
	isort-check \
	lint \
	mypy-check \
	show-certificate \
	test \
	veryclean

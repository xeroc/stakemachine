.PHONY: clean-pyc clean-build docs

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr __pycache__/

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
pip:
	python3 -m pip install -r requirements.txt

lint:
	flake8 dexbot/

build: pip
	python3 setup.py build

install: build
	python3 setup.py install

install-user: build
	python3 setup.py install --user

git:
	git push --all
	git push --tags

check: pip
	python3 setup.py check

package: build
	pyinstaller app.spec
	pyinstaller cli.spec

dist: pip
	python3 setup.py sdist upload -r pypi
	python3 setup.py bdist_wheel upload

release: clean check dist git

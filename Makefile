.PHONY: clean-pyc clean-build docs

TAG := $(shell git describe master --abbrev=0)
TAGSTEEM := $(shell git describe master --abbrev=0 | tr "." "-")

# 
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

lint:
	flake8 stakemachine/

build:
	python3 setup.py build

install: build
	python3 setup.py install

install-user: build
	python3 setup.py install --user

git:
	git push --all
	git push --tags

check:
	python3 setup.py check

dist:
	python3 setup.py sdist upload -r pypi
	python3 setup.py bdist --format=zip upload

release: clean check dist steem-readme steem-changelog git

steem-readme:
	piston edit "@xeroc/stakemachine-readme" --file README.md

steem-changelog:
	git tag -l -n100 $(TAG) | piston post --author xeroc --permlink "stakemachine-changelog-$(TAGSTEEM)" --category steem --title "[Changelog] StakeMachine $(TAG)" \

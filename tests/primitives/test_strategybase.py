import logging

import pytest

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


@pytest.fixture()
def worker(strategybase):
    return strategybase


@pytest.mark.mandatory
def test_init(worker):
    pass

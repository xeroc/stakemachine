import logging

import pytest

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


@pytest.fixture()
def worker(strategybase):
    return strategybase


def test_init(worker):
    pass

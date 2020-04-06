import logging

import pytest

from dexbot.storage import Storage

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


@pytest.fixture
def storage():
    worker_name = 'test_worker'
    yield Storage(worker_name)
    Storage.clear_worker_data(worker_name)

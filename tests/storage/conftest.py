import logging
import os
import tempfile

import pytest
from dexbot.storage import Storage

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


@pytest.fixture
def storage():
    worker_name = 'test_worker'
    _, db_file = tempfile.mkstemp()  # noqa: F811
    storage = Storage(worker_name, db_file=db_file)
    yield storage
    os.unlink(db_file)

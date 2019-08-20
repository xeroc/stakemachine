import os
import pytest
import tempfile
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


@pytest.fixture
def initial_db():

    _, db_file = tempfile.mkstemp()  # noqa: F811
    engine = create_engine('sqlite:///{}'.format(db_file), echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.commit()
    log.debug('Prepared db on {}'.format(db_file))

    yield db_file
    os.unlink(db_file)

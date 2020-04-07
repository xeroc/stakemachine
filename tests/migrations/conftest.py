import logging
import os
import tempfile

import pytest
from dexbot.storage import DatabaseWorker
from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)

Base = declarative_base()

# Classes are represent initial table structure


class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    category = Column(String)
    key = Column(String)
    value = Column(String)


class Orders(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    worker = Column(String)
    order_id = Column(String)
    order = Column(String)


class Balances(Base):
    __tablename__ = 'balances'

    id = Column(Integer, primary_key=True)
    account = Column(String)
    worker = Column(String)
    base_total = Column(Float)
    base_symbol = Column(String)
    quote_total = Column(Float)
    quote_symbol = Column(String)
    center_price = Column(Float)
    timestamp = Column(Integer)


@pytest.fixture
def fresh_db():

    _, db_file = tempfile.mkstemp()  # noqa: F811
    _ = DatabaseWorker(db_file)
    yield db_file
    os.unlink(db_file)


@pytest.fixture
def historic_db():

    _, db_file = tempfile.mkstemp()  # noqa: F811
    engine = create_engine('sqlite:///{}'.format(db_file), echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    Base.metadata.create_all(engine)
    session.commit()
    log.debug('Prepared db on {}'.format(db_file))

    yield db_file
    os.unlink(db_file)

import sqlalchemy
import os
import json
import threading
import queue
import uuid
import time
from sqlalchemy import create_engine, Table, Column, String, Integer, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from appdirs import user_data_dir
Base = declarative_base()

# For dexbot.sqlite file
appname = "dexbot"
appauthor = "ChainSquad GmbH"
storageDatabase = "dexbot.sqlite"


def mkdir_p(d):
    if os.path.isdir(d):
        return
    else:
        try:
            os.makedirs(d)
        except FileExistsError:
            return
        except OSError:
            raise


class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    category = Column(String)
    key = Column(String)
    value = Column(String)

    def __init__(self, c, k, v):
        self.category = c
        self.key = k
        self.value = v


class Storage(dict):
    """ Storage class

        :param string category: The category to distinguish
                                different storage namespaces
    """
    def __init__(self, category):
        self.category = category

    def __setitem__(self, key, value):
        db_worker.execute_noreturn(db_worker.set_item, self.category, key, value)

    def __getitem__(self, key):
        return db_worker.execute(db_worker.get_item, self.category, key)

    def __delitem__(self, key):
        db_worker.execute_noreturn(db_worker.del_item, self.category, key)

    def __contains__(self, key):
        return db_worker.execute(db_worker.contains, self.category, key)

    def items(self):
        return db_worker.execute(db_worker.get_items, self.category)

    def clear(self):
        db_worker.execute_noreturn(db_worker.clear, self.category)


class DatabaseWorker(threading.Thread):
    """
    Thread safe database worker
    """

    def __init__(self):
        super().__init__()

        # Obtain engine and session
        engine = create_engine('sqlite:///%s' % sqlDataBaseFile, echo=False)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        Base.metadata.create_all(engine)
        self.session.commit()

        self.task_queue = queue.Queue()
        self.results = {}

        self.lock = threading.Lock()
        self.event = threading.Event()
        self.daemon = True
        self.start()

    def run(self):
        for func, args, token in iter(self.task_queue.get, None):
            if token is not None:
                args = args+(token,)
            func(*args)

    def get_result(self, token):
        while True:
            with self.lock:
                if token in self.results:
                    return_value = self.results[token]
                    del self.results[token]
                    return return_value
                else:
                    self.event.clear()
            self.event.wait()

    def set_result(self, token, result):
        with self.lock:
            self.results[token] = result
            self.event.set()

    def execute(self, func, *args):
        token = str(uuid.uuid4)
        self.task_queue.put((func, args, token))
        return self.get_result(token)

    def execute_noreturn(self, func, *args):
        self.task_queue.put((func, args, None))
        
    def set_item(self, category, key, value):
        value = json.dumps(value)
        e = self.session.query(Config).filter_by(
            category=category,
            key=key
        ).first()
        if e:
            e.value = value
        else:
            e = Config(category, key, value)
            self.session.add(e)
        self.session.commit()

    def get_item(self, category, key, token):
        e = self.session.query(Config).filter_by(
            category=category,
            key=key
        ).first()
        if not e:
            result = None
        else:
            result = json.loads(e.value)
        self.set_result(token, result)

    def del_item(self, category, key):
        e = self.session.query(Config).filter_by(
            category=category,
            key=key
        ).first()
        self.session.delete(e)
        self.session.commit()

    def contains(self, category, key, token):
        e = self.session.query(Config).filter_by(
            category=category,
            key=key
        ).first()
        self.set_result(token, bool(e))

    def get_items(self, category, token):
        es = self.session.query(Config).filter_by(
            category=category
        ).all()
        result = [(e.key, e.value) for e in es]
        self.set_result(token, result)

    def clear(self, category):
        rows = self.session.query(Config).filter_by(
            category=category
        )
        for row in rows:
            self.session.delete(row)
            self.session.commit()


# Derive sqlite file directory
data_dir = user_data_dir(appname, appauthor)
sqlDataBaseFile = os.path.join(data_dir, storageDatabase)

# Create directory for sqlite file
mkdir_p(data_dir)

db_worker = DatabaseWorker()

import os
import os.path
import inspect
import json
import threading
import queue
import uuid
import alembic
import alembic.config

from appdirs import user_data_dir

from . import helper
from dexbot import APP_NAME, AUTHOR

from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, load_only


Base = declarative_base()

# For dexbot.sqlite file
storageDatabase = "dexbot.sqlite"


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


class Orders(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    worker = Column(String)
    order_id = Column(String)
    order = Column(String)
    virtual = Column(Boolean)
    custom = Column(String)

    def __init__(self, worker, order_id, order, virtual, custom):
        self.worker = worker
        self.order_id = order_id
        self.order = order
        self.virtual = virtual
        self.custom = custom


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

    def __init__(self, account, worker, base_total, base_symbol, quote_total, quote_symbol, center_price, timestamp):
        self.account = account
        self.worker = worker
        self.base_total = base_total
        self.base_symbol = base_symbol
        self.quote_total = quote_total
        self.quote_symbol = quote_symbol
        self.center_price = center_price
        self.timestamp = timestamp


class Storage(dict):
    """ Storage class

        :param string category: The category to distinguish
                                different storage namespaces
    """

    def __init__(self, category):
        self.category = category

    def __setitem__(self, key, value):
        db_worker.set_item(self.category, key, value)

    def __getitem__(self, key):
        return db_worker.get_item(self.category, key)

    def __delitem__(self, key):
        db_worker.del_item(self.category, key)

    def __contains__(self, key):
        return db_worker.contains(self.category, key)

    def items(self):
        return db_worker.get_items(self.category)

    def clear(self):
        db_worker.clear(self.category)

    def save_order(self, order):
        """ Save the order to the database
        """
        order_id = order['id']
        db_worker.save_order(self.category, order_id, order)

    def save_order_extended(self, order, virtual=None, custom=None):
        """ Save the order to the database providing additional data

            :param dict order:
            :param bool virtual: True = order is virtual order
            :param str custom: any additional data
        """
        order_id = order['id']
        db_worker.save_order_extended(self.category, order_id, order, virtual, custom)

    def remove_order(self, order):
        """ Removes an order from the database
        """
        order_id = order['id']
        db_worker.remove_order(self.category, order_id)

    def clear_orders(self):
        """ Removes all worker's orders from the database
        """
        db_worker.clear_orders(self.category)

    def fetch_orders(self, worker=None):
        """ Get all the orders (or just specific worker's orders) from the database

            :param str worker: worker name (None means current worker name will be used)
        """
        if not worker:
            worker = self.category
        return db_worker.fetch_orders(worker)

    def fetch_orders_extended(self, worker=None, only_virtual=False, only_real=False, custom=None,
                              return_ids_only=False):
        """ Get orders from the database in extended format (returning all columns)

            :param str worker: worker name (None means current worker name will be used)
            :param bool only_virtual: True = fetch only virtual orders
            :param bool only_real: True = fetch only real orders
            :param str custom: filter orders by custom field
            :param bool return_ids_only: instead of returning full row data, return only order ids
            :rtype: list
            :return: list of dicts in format [{order_id: '', order: '', virtual: '', custom: ''}], or [order_id] if
                return_ids_only used
        """
        if only_virtual and only_real:
            raise ValueError('only_virtual and only_real are mutually exclusive')
        if not worker:
            worker = self.category
        return db_worker.fetch_orders_extended(worker, only_virtual, only_real, custom, return_ids_only)

    @staticmethod
    def clear_worker_data(worker):
        db_worker.clear_orders(worker)
        db_worker.clear(worker)

    @staticmethod
    def store_balance_entry(account, worker, base_total, base_symbol, quote_total, quote_symbol,
                            center_price, timestamp):
        balance = Balances(account, worker, base_total, base_symbol,
                           quote_total, quote_symbol, center_price, timestamp)
        # Save balance to db
        db_worker.save_balance(balance)

    @staticmethod
    def get_balance_history(account, worker, timestamp, base_asset, quote_asset):
        return db_worker.get_balance(account, worker, timestamp, base_asset, quote_asset)

    @staticmethod
    def get_recent_balance_entry(account, worker, base_asset, quote_asset):
        return db_worker.get_recent_balance_entry(account, worker, base_asset, quote_asset)


class DatabaseWorker(threading.Thread):
    """ Thread safe database worker
    """

    def __init__(self):
        super().__init__()

        # Obtain engine and session
        dsn = 'sqlite:///{}'.format(sqlDataBaseFile)
        engine = create_engine(dsn, echo=False)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        Base.metadata.create_all(engine)
        self.session.commit()

        # Run migrations
        import dexbot
        migrations_dir = '{}/migrations'.format(os.path.dirname(inspect.getfile(dexbot)))
        self.run_migrations(migrations_dir, dsn)

        self.task_queue = queue.Queue()
        self.results = {}

        self.lock = threading.Lock()
        self.event = threading.Event()
        self.daemon = True
        self.start()

    @staticmethod
    def run_migrations(script_location, dsn):
        """ Apply database migrations using alembic

            :param str script_location: path to migration scripts
            :param str dsn: database URL
        """
        alembic_cfg = alembic.config.Config()
        alembic_cfg.set_main_option('script_location', script_location)
        alembic_cfg.set_main_option('sqlalchemy.url', dsn)
        alembic.command.upgrade(alembic_cfg, 'head')

    def run(self):
        for func, args, token in iter(self.task_queue.get, None):
            if token is not None:
                args = args+(token,)
            func(*args)

    def _get_result(self, token):
        while True:
            with self.lock:
                if token in self.results:
                    return_value = self.results[token]
                    del self.results[token]
                    return return_value
                else:
                    self.event.clear()
            self.event.wait()

    def _set_result(self, token, result):
        with self.lock:
            self.results[token] = result
            self.event.set()

    def execute(self, func, *args):
        token = str(uuid.uuid4)
        self.task_queue.put((func, args, token))
        return self._get_result(token)

    def execute_noreturn(self, func, *args):
        self.task_queue.put((func, args, None))

    def set_item(self, category, key, value):
        self.execute_noreturn(self._set_item, category, key, value)

    def _set_item(self, category, key, value):
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

    def get_item(self, category, key):
        return self.execute(self._get_item, category, key)

    def _get_item(self, category, key, token):
        e = self.session.query(Config).filter_by(
            category=category,
            key=key
        ).first()
        if not e:
            result = None
        else:
            result = json.loads(e.value)
        self._set_result(token, result)

    def del_item(self, category, key):
        self.execute_noreturn(self._del_item, category, key)

    def _del_item(self, category, key):
        e = self.session.query(Config).filter_by(
            category=category,
            key=key
        ).first()
        self.session.delete(e)
        self.session.commit()

    def contains(self, category, key):
        return self.execute(self._contains, category, key)

    def _contains(self, category, key, token):
        e = self.session.query(Config).filter_by(
            category=category,
            key=key
        ).first()
        self._set_result(token, bool(e))

    def get_items(self, category):
        return self.execute(self._get_items, category)

    def _get_items(self, category, token):
        es = self.session.query(Config).filter_by(
            category=category
        ).all()
        result = [(e.key, e.value) for e in es]
        self._set_result(token, result)

    def clear(self, category):
        self.execute_noreturn(self._clear, category)

    def _clear(self, category):
        rows = self.session.query(Config).filter_by(
            category=category
        )
        for row in rows:
            self.session.delete(row)
            self.session.commit()

    def save_order(self, worker, order_id, order):
        self.execute_noreturn(self._save_order, worker, order_id, order)

    def _save_order(self, worker, order_id, order):
        value = json.dumps(order)
        e = self.session.query(Orders).filter_by(
            order_id=order_id
        ).first()
        if e:
            e.value = value
        else:
            e = Orders(worker, order_id, value, None, None)
            self.session.add(e)
        self.session.commit()

    def save_order_extended(self, worker, order_id, order, virtual, custom):
        self.execute_noreturn(self._save_order_extended, worker, order_id, order, virtual, custom)

    def _save_order_extended(self, worker, order_id, order, virtual, custom):
        order_json = json.dumps(order)
        custom_json = json.dumps(custom)
        e = self.session.query(Orders).filter_by(
            order_id=order_id
        ).first()
        if e:
            e.order = order_json
            e.virtual = virtual
            e.custom = custom_json
        else:
            e = Orders(worker, order_id, order_json, virtual, custom_json)
            self.session.add(e)
        self.session.commit()

    def remove_order(self, worker, order_id):
        self.execute_noreturn(self._remove_order, worker, order_id)

    def _remove_order(self, worker, order_id):
        e = self.session.query(Orders).filter_by(
            worker=worker,
            order_id=order_id
        ).first()
        self.session.delete(e)
        self.session.commit()

    def clear_orders(self, worker):
        self.execute_noreturn(self._clear_orders, worker)

    def _clear_orders(self, worker):
        rows = self.session.query(Orders).filter_by(
            worker=worker
        )
        for row in rows:
            self.session.delete(row)
            self.session.commit()

    def fetch_orders(self, category):
        return self.execute(self._fetch_orders, category)

    def _fetch_orders(self, worker, token):
        results = self.session.query(Orders).filter_by(
            worker=worker,
        ).all()
        if not results:
            result = None
        else:
            result = {}
            for row in results:
                result[row.order_id] = json.loads(row.order)
        self._set_result(token, result)

    def fetch_orders_extended(self, category, only_virtual, only_real, custom, return_ids_only):
        return self.execute(self._fetch_orders_extended, category, only_virtual, only_real, custom, return_ids_only)

    def _fetch_orders_extended(self, worker, only_virtual, only_real, custom, return_ids_only, token):
        filter_by = {'worker': worker}
        if only_virtual:
            filter_by['virtual'] = True
        elif only_real:
            filter_by['virtual'] = False
        if custom:
            filter_by['custom'] = json.dumps(custom)

        if return_ids_only:
            query = self.session.query(Orders).options(load_only('order_id'))
            results = query.filter_by(**filter_by).all()
            result = [row.order_id for row in results]
        else:
            results = self.session.query(Orders).filter_by(**filter_by).all()
            result = []
            for row in results:
                entry = {'order_id': row.order_id, 'order': json.loads(row.order), 'virtual': row.virtual,
                         'custom': json.loads(row.custom)}
                result.append(entry)

        self._set_result(token, result)

    def save_balance(self, balance):
        self.execute_noreturn(self._save_balance, balance)

    def _save_balance(self, balance):
        self.session.add(balance)
        self.session.commit()

    def get_balance(self, account, worker, timestamp, base_asset, quote_asset):
        return self.execute(self._get_balance, account, worker, timestamp, base_asset, quote_asset)

    def _get_balance(self, account, worker, timestamp, base_asset, quote_asset, token):
        """ Get first item that has bigger time as given timestamp and matches account and worker name
        """
        result = self.session.query(Balances).filter(
            Balances.account == account,
            Balances.worker == worker,
            Balances.base_symbol == base_asset,
            Balances.quote_symbol == quote_asset,
            Balances.timestamp > timestamp
        ).first()

        self._set_result(token, result)

    def get_recent_balance_entry(self, account, worker, base_asset, quote_asset):
        return self.execute(self._get_recent_balance_entry, account, worker, base_asset, quote_asset)

    def _get_recent_balance_entry(self, account, worker, base_asset, quote_asset, token):
        """ Get most recent balance history item that matches account and worker name
        """
        result = self.session.query(Balances).filter(
            Balances.account == account,
            Balances.worker == worker,
            Balances.base_symbol == base_asset,
            Balances.quote_symbol == quote_asset,
        ).order_by(Balances.id.desc()).first()

        self._set_result(token, result)


# Derive sqlite file directory
data_dir = user_data_dir(APP_NAME, AUTHOR)
sqlDataBaseFile = os.path.join(data_dir, storageDatabase)

# Create directory for sqlite file
helper.mkdir(data_dir)

db_worker = DatabaseWorker()

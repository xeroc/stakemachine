import logging
import tempfile

import pytest
from dexbot.storage import Storage

log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)

pytestmark = pytest.mark.mandatory


def test_init(storage):

    # Storage instances with same db_file using single DatabaseWorker()
    _, db_file = tempfile.mkstemp()  # noqa: F811
    storage1 = Storage('test', db_file=db_file)
    storage2 = Storage('test2', db_file=db_file)
    assert storage1.db_worker is storage2.db_worker

    # Different db files - different DatabaseWorker()
    storage3 = Storage('test')
    assert storage3.db_worker is not storage1.db_worker


def test_get_default_db_file(storage):
    file_ = storage.get_default_db_file()
    assert isinstance(file_, str)


def test_fetch_orders(storage):
    order = {'id': '111', 'base': '10 CNY', 'quote': '1 BTS'}
    storage.save_order(order)
    fetched = storage.fetch_orders()
    # Return value is dict {'id': 'order'}
    assert fetched[order['id']] == order


def test_fetch_orders_extended(storage):
    order = {'id': '111', 'base': '10 CNY', 'quote': '1 BTS'}
    text = 'foo bar'
    storage.save_order_extended(order, virtual=True, custom=text)

    fetched = storage.fetch_orders_extended(only_real=True)
    assert len(fetched) == 0
    fetched = storage.fetch_orders_extended(only_virtual=True)
    assert len(fetched) == 1
    fetched = storage.fetch_orders_extended(custom=text)
    assert len(fetched) == 1
    fetched = storage.fetch_orders_extended(return_ids_only=True)
    assert fetched == ['111']

    fetched = storage.fetch_orders_extended()
    assert isinstance(fetched, list)
    result = fetched[0]
    assert result['custom'] == 'foo bar'
    assert result['virtual'] is True
    assert result['order'] == order


def test_clear_orders(storage):
    order = {'id': '111', 'base': '10 CNY', 'quote': '1 BTS'}
    storage.save_order(order)
    storage.clear_orders()
    fetched = storage.fetch_orders()
    assert fetched is None


def test_clear_orders_extended(storage):
    order = {'id': '111', 'base': '10 CNY', 'quote': '1 BTS'}
    storage.save_order_extended(order, virtual=True)
    storage.clear_orders_extended(only_virtual=True)
    fetched = storage.fetch_orders_extended()
    assert fetched == []

    storage.save_order_extended(order, custom='foo')
    storage.clear_orders_extended(custom='foo')
    fetched = storage.fetch_orders_extended()
    assert fetched == []


def test_remove_order(storage):
    order = {'id': '111', 'base': '10 CNY', 'quote': '1 BTS'}
    storage.save_order(order)
    storage.remove_order(order)
    assert storage.fetch_orders() is None


def test_remove_order_by_id(storage):
    order = {'id': '111', 'base': '10 CNY', 'quote': '1 BTS'}
    storage.save_order(order)
    storage.remove_order(order['id'])
    assert storage.fetch_orders() is None

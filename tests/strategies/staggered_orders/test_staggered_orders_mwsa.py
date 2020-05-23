import logging

import pytest

# Turn on debug for dexbot logger
log = logging.getLogger("dexbot")
log.setLevel(logging.DEBUG)


def test_mwsa_base_intersection(base_worker, config_multiple_workers_1, do_initial_allocation):
    """Check if workers usage of BASE asset is equal."""
    worker1 = base_worker(config_multiple_workers_1, worker_name="so-worker-1")
    worker2 = base_worker(config_multiple_workers_1, worker_name="so-worker-2")
    do_initial_allocation(worker1, worker1.mode)
    do_initial_allocation(worker2, worker2.mode)

    assert worker1.base_total_balance == pytest.approx(worker2.base_total_balance)


def test_mwsa_quote_intersection(base_worker, config_multiple_workers_2, do_initial_allocation):
    """Check if workers usage of QUOTE asset is equal."""
    worker1 = base_worker(config_multiple_workers_2, worker_name="so-worker-1")
    worker2 = base_worker(config_multiple_workers_2, worker_name="so-worker-2")
    do_initial_allocation(worker1, worker1.mode)
    do_initial_allocation(worker2, worker2.mode)

    assert worker1.quote_total_balance == pytest.approx(worker2.quote_total_balance)


def test_mwsa_manual_base_percent(base_worker, config_multiple_workers_1, do_initial_allocation):
    """Check if workers usage of BASE asset is in accordance with op_percent setting."""
    worker1 = base_worker(config_multiple_workers_1, worker_name="so-worker-1")
    worker2 = base_worker(config_multiple_workers_1, worker_name="so-worker-2")
    worker1.operational_percent_base = 0.8
    worker2.operational_percent_base = 0.2
    do_initial_allocation(worker1, worker1.mode)
    do_initial_allocation(worker2, worker2.mode)

    total = worker1.base_total_balance + worker2.base_total_balance

    assert worker1.base_total_balance / total == pytest.approx(worker1.operational_percent_base)
    assert worker2.base_total_balance / total == pytest.approx(worker2.operational_percent_base)


def test_mwsa_manual_quote_percent(base_worker, config_multiple_workers_2, do_initial_allocation):
    """Check if workers usage of QUOTE asset is in accordance with op_percent setting."""
    worker1 = base_worker(config_multiple_workers_2, worker_name="so-worker-1")
    worker2 = base_worker(config_multiple_workers_2, worker_name="so-worker-2")
    worker1.operational_percent_quote = 0.8
    worker2.operational_percent_quote = 0.2
    do_initial_allocation(worker1, worker1.mode)
    do_initial_allocation(worker2, worker2.mode)

    total = worker1.quote_total_balance + worker2.quote_total_balance

    assert worker1.quote_total_balance / total == pytest.approx(worker1.operational_percent_quote)
    assert worker2.quote_total_balance / total == pytest.approx(worker2.operational_percent_quote)

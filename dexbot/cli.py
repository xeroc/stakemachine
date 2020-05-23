#!/usr/bin/env python3
import logging
import os
import os.path
import signal
import sys
import time
from multiprocessing import freeze_support

import bitshares.exceptions
import click  # noqa: E402
import graphenecommon.exceptions
from bitshares.market import Market
from uptick.decorators import online

from dexbot.cli_conf import SYSTEMD_SERVICE_NAME, get_whiptail, setup_systemd
from dexbot.config import DEFAULT_CONFIG_FILE, Config
from dexbot.helper import initialize_data_folders, initialize_orders_log
from dexbot.storage import Storage
from dexbot.ui import chain, configfile, reset_nodes, unlock, verbose

from . import errors, helper
from .cli_conf import configure_dexbot, dexbot_service_running
from .worker import WorkerInfrastructure

# We need to do this before importing click
if "LANG" not in os.environ:
    os.environ['LANG'] = 'C.UTF-8'


log = logging.getLogger(__name__)

# Initial logging before proper setup.
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Configure orders logging
initialize_orders_log()

# Initialize data folders
initialize_data_folders()


@click.group()
@click.option(
    "--configfile", default=DEFAULT_CONFIG_FILE,
)
@click.option(
    '--logfile',
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help='Override logfile location (example: ~/dexbot.log)',
)
@click.option('--verbose', '-v', type=int, default=3, help='Verbosity (0-15)')
@click.option('--systemd/--no-systemd', '-d', default=False, help='Run as a daemon from systemd')
@click.option('--pidfile', '-p', type=click.Path(dir_okay=False, writable=True), default='', help='File to write PID')
@click.option('--sortnodes', '-s', type=int, default=-1, help='Sort nodes, w/max timeout in sec. [sec > 0]')
@click.pass_context
def main(ctx, **kwargs):
    ctx.obj = {}
    for k, v in kwargs.items():
        ctx.obj[k] = v


@main.command()
@click.pass_context
@reset_nodes
def resetnodes(ctx):
    """Reset nodes to the default list, use -s option to sort."""
    log.info("Resetting node list in config.yml to default list")
    log.info("To sort nodes by timeout, use: `dexbot-cli -s 2 resetnodes`")


@main.command()
@click.pass_context
@configfile
@chain
@unlock
@verbose
def run(ctx):
    """Continuously run the worker."""
    if ctx.obj['pidfile']:
        with open(ctx.obj['pidfile'], 'w') as fd:
            fd.write(str(os.getpid()))
    try:
        worker = WorkerInfrastructure(ctx.config)
        # Set up signalling. do it here as of no relevance to GUI
        kill_workers = worker_job(worker, lambda: worker.stop(pause=True))
        # These first two UNIX & Windows
        signal.signal(signal.SIGTERM, kill_workers)
        signal.signal(signal.SIGINT, kill_workers)
        try:
            # These signals are UNIX-only territory, will ValueError or AttributeError here on Windows (depending on
            # python version)
            signal.signal(signal.SIGHUP, kill_workers)
            # TODO: reload config on SIGUSR1
            # signal.signal(signal.SIGUSR1, lambda x, y: worker.do_next_tick(worker.reread_config))
        except (ValueError, AttributeError):
            log.debug("Cannot set all signals -- not available on this platform")
        if ctx.obj['systemd']:
            try:
                import sdnotify  # A soft dependency on sdnotify -- don't crash on non-systemd systems

                n = sdnotify.SystemdNotifier()
                n.notify("READY=1")
            except BaseException:
                log.debug("sdnotify not available")
        worker.run()
    except errors.NoWorkersAvailable:
        sys.exit(70)  # 70= "Software error" in /usr/include/sysexts.h
    finally:
        if ctx.obj['pidfile']:
            helper.remove(ctx.obj['pidfile'])


@main.command()
@click.pass_context
@configfile
@chain
@unlock
def runservice():
    """Continuously run the worker as a service."""
    if dexbot_service_running():
        click.echo("Stopping dexbot daemon")
        os.system('systemctl --user stop dexbot')

    if not os.path.exists(SYSTEMD_SERVICE_NAME):
        setup_systemd(get_whiptail('DEXBot configure'), {})

    click.echo("Starting dexbot daemon")
    os.system("systemctl --user start dexbot")


@main.command()
@click.pass_context
@configfile
@chain
@unlock
def configure(ctx):
    """Interactively configure dexbot."""
    # Make sure the dexbot service isn't running while we do the config edits
    if dexbot_service_running():
        click.echo("Stopping dexbot daemon")
        os.system('systemctl --user stop dexbot')

    config = Config(path=ctx.obj['configfile'])
    configure_dexbot(config, ctx)
    config.save_config()

    click.echo("New configuration saved")
    if config.get('systemd_status', 'disabled') == 'enabled':
        click.echo("Starting dexbot daemon")
        os.system("systemctl --user start dexbot")


@main.command()
@click.option("--account", default=None)
@click.argument("market")
@click.pass_context
@online
@unlock
def cancel(ctx, market, account):
    """
    Cancel Orders in Mkt, (Eg: cancel USD/BTS --account name)

    :param ctx: context
    :param market: market e.g. USD/BTS
    :param account: name of your bitshares acct
    :return: Success or Fail message
    """
    try:
        my_market = Market(market)
        ctx.bitshares.bundle = True
        my_market.cancel([x["id"] for x in my_market.accountopenorders(account)], account=account)
        response = ctx.bitshares.txbuffer.broadcast()
        log.info(response)
        if response is not None:
            log.info(f'Cancelled all orders on Market: {market} for account: {account}')
        else:
            log.info(f'No orders to cancel! {market} for account: {account}')

    except bitshares.exceptions.AssetDoesNotExistsException:
        log.info(f"Asset does not exist: {market}")
    except graphenecommon.exceptions.AccountDoesNotExistsException:
        log.info(f"Account does not exist: {account}")


@click.argument('worker_name')
def drop_state(worker_name):
    """Drop state of the worker (sqlite data)"""
    click.echo('Dropping state for {}'.format(worker_name))
    storage = Storage(worker_name)
    storage.clear_worker_data()
    time.sleep(1)


def worker_job(worker, job):
    return lambda x, y: worker.do_next_tick(job)


if __name__ == '__main__':
    """
    Add freeze_support for when a program which uses multiprocessing (node_manager) has been frozen to produce a Windows
    executable.

    If the freeze_support() line is omitted then trying to run the frozen executable will raise RuntimeError. Calling
    freeze_support() has no effect when invoked on any operating system other than Windows.
    """
    freeze_support()
    main()

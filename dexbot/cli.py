#!/usr/bin/env python3
import logging
import os
import os.path
import signal
import sys

from dexbot.config import Config, DEFAULT_CONFIG_FILE
from dexbot.ui import (
    verbose,
    chain,
    unlock,
    configfile
)
from .worker import WorkerInfrastructure
from .cli_conf import configure_dexbot
from . import errors
from . import helper

from ruamel import yaml
# We need to do this before importing click
if "LANG" not in os.environ:
    os.environ['LANG'] = 'C.UTF-8'
import click


log = logging.getLogger(__name__)

# Initial logging before proper setup.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


@click.group()
@click.option(
    "--configfile",
    default=DEFAULT_CONFIG_FILE,
)
@click.option(
    '--verbose',
    '-v',
    type=int,
    default=3,
    help='Verbosity (0-15)')
@click.option(
    '--systemd/--no-systemd',
    '-d',
    default=False,
    help='Run as a daemon from systemd')
@click.option(
    '--pidfile',
    '-p',
    type=str,
    default='',
    help='File to write PID')
@click.pass_context
def main(ctx, **kwargs):
    ctx.obj = {}
    for k, v in kwargs.items():
        ctx.obj[k] = v


@main.command()
@click.pass_context
@configfile
@chain
@unlock
@verbose
def run(ctx):
    """ Continuously run the worker
    """
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
            # These signals are UNIX-only territory, will ValueError here on Windows
            signal.signal(signal.SIGHUP, kill_workers)
            # TODO: reload config on SIGUSR1
            # signal.signal(signal.SIGUSR1, lambda x, y: worker.do_next_tick(worker.reread_config))
        except ValueError:
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
def configure(ctx):
    """ Interactively configure dexbot
    """
    config = Config(ctx.obj['configfile'])
    configure_dexbot(config)
    config.save_config()

    click.echo("New configuration saved")
    if config['systemd_status'] == 'installed':
        # we are already installed
        click.echo("Restarting dexbot daemon")
        os.system("systemctl --user restart dexbot")
    if config['systemd_status'] == 'install':
        os.system("systemctl --user enable dexbot")
        click.echo("Starting dexbot daemon")
        os.system("systemctl --user start dexbot")


def worker_job(worker, job):
    return lambda x, y: worker.do_next_tick(job)


if __name__ == '__main__':
    main()

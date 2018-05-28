#!/usr/bin/env python3
import logging
import os
import os.path
import sys
import signal

# we need to do this before importing click
if not "LANG" in os.environ:
    os.environ['LANG'] = 'C.UTF-8'
import click
import appdirs
from ruamel import yaml

from dexbot import config_file, default_config
from dexbot.ui import (
    verbose,
    chain,
    unlock,
    configfile
)
from dexbot.cli_conf import configure_dexbot
from dexbot import storage
from dexbot.worker import WorkerInfrastructure
import dexbot.errors as errors


log = logging.getLogger(__name__)

# inital logging before proper setup.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


@click.group()
@click.option(
    "--configfile",
    default=config_file,
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
        try:
            worker = WorkerInfrastructure(ctx.config)
            # Set up signalling. do it here as of no relevance to GUI
            kill_workers = worker_job(worker, worker.stop)
            # These first two UNIX & Windows
            signal.signal(signal.SIGTERM, kill_workers)
            signal.signal(signal.SIGINT, kill_workers)
            try:
                # These signals are UNIX-only territory, will ValueError here on Windows
                signal.signal(signal.SIGHUP, kill_workers)
                # TODO: reload config on SIGUSR1
                # signal.signal(signal.SIGUSR1, lambda x, y: worker.do_next_tick(worker.reread_config))
            except AttributeError:
                log.debug("Cannot set all signals -- not available on this platform")
            worker.init_workers(ctx.config)
            if ctx.obj['systemd']:  # tell systemd we are running
                try:
                    import sdnotify  # a soft dependency on sdnotify -- don't crash on non-systemd systems
                    n = sdnotify.SystemdNotifier()
                    n.notify("READY=1")
                except BaseException:
                    log.debug("sdnotify not available")
            worker.update_notify()
            worker.notify.listen()
        finally:
            if ctx.obj['pidfile']:
                os.unlink(ctx.obj['pidfile'])
    except errors.NoWorkersAvailable:
        sys.exit(70)  # 70= "Software error" in /usr/include/sysexts.h
        # this needs to be in an outside try otherwise we will exit before the finally clause


@main.command()
@click.pass_context
def configure(ctx):
    """ Interactively configure dexbot
    """
    cfg_file = ctx.obj["configfile"]
    if not os.path.exists(ctx.obj['configfile']):
        storage.mkdir_p(os.path.dirname(ctx.obj['configfile']))
        with open(ctx.obj['configfile'], 'w') as fd:
            fd.write(default_config)
    with open(ctx.obj["configfile"]) as fd:
        config = yaml.safe_load(fd)
    configure_dexbot(config)
    with open(cfg_file, "w") as fd:
        yaml.dump(config, fd, default_flow_style=False)
    click.echo("new configuration saved")
    if config['systemd_status'] == 'installed':
        # we are already installed
        click.echo("restarting dexbot daemon")
        os.system("systemctl --user restart dexbot")
    if config['systemd_status'] == 'install':
        os.system("systemctl --user enable dexbot")
        click.echo("starting dexbot daemon")
        os.system("systemctl --user start dexbot")


def worker_job(worker, job):
    return lambda x, y: worker.do_next_tick(job)


if __name__ == '__main__':
    main()

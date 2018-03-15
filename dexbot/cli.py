#!/usr/bin/env python3
import logging
import os
# we need to do this before importing click
if not "LANG" in os.environ:
    os.environ['LANG'] = 'C.UTF-8'
import click
import os.path
import os
import sys
import appdirs
from ruamel import yaml

from .ui import (
    verbose,
    chain,
    unlock,
    configfile,
    confirmwarning,
    confirmalert,
    warning,
    alert,
)

from .bot import BotInfrastructure
from .cli_conf import configure_dexbot
from . import errors
from . import storage

log = logging.getLogger(__name__)

# inital logging before proper setup.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


@click.group()
@click.option(
    "--configfile",
    default=os.path.join(appdirs.user_config_dir("dexbot"),"config.yml"),
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
    """ Continuously run the bot
    """
    if ctx.obj['pidfile']:
        with open(ctx.obj['pidfile'],'w') as fd:
            fd.write(str(os.getpid()))
    try:
        bot = BotInfrastructure(ctx.config)
        bot.init_bots()
        if ctx.obj['systemd']:
            try:
                import sdnotify  # a soft dependency on sdnotify -- don't crash on non-systemd systems
                n = sdnotify.SystemdNotifier()
                n.notify("READY=1")
            except BaseException:
                log.debug("sdnotify not available")
        bot.notify.listen()
    except errors.NoBotsAvailable:
        sys.exit(70)  # 70= "Software error" in /usr/include/sysexts.h


@main.command()
@click.pass_context
def configure(ctx):
    """ Interactively configure dexbot
    """
    cfg_file = ctx.obj["configfile"]
    if os.path.exists(ctx.obj['configfile']):
        with open(ctx.obj["configfile"]) as fd:
            config = yaml.safe_load(fd)
    else:
        config = {}
        storage.mkdir_p(os.path.dirname(ctx.obj['configfile']))
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

if __name__ == '__main__':
    main()

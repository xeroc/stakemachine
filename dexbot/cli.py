#!/usr/bin/env python3
import logging
import os
import click
import sys
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
from dexbot.bot import BotInfrastructure
import dexbot.errors as errors

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


@click.group()
@click.option(
    "--configfile",
    default="config.yml",
)
@click.option(
    '--verbose',
    '-v',
    type=int,
    default=3,
    help='Verbosity (0-15)')
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
        with open(ctx.obj['pidfile'], 'w') as fd:
            fd.write(str(os.getpid()))
    try:
        bot = BotInfrastructure(ctx.config)
        bot.run()
    except errors.NoBotsAvailable:
        sys.exit(70)  # 70= "Software error" in /usr/include/sysexts.h


if __name__ == '__main__':
    main()

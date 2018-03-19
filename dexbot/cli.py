#!/usr/bin/env python3
import logging
import click
import signal
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
    try:
        bot = BotInfrastructure(ctx.config)
        # Set up signalling. do it here as of no relevance to GUI
        kill_bots = bot_job(bot, bot.stop)
        # These first two UNIX & Windows
        signal.signal(signal.SIGTERM, kill_bots)
        signal.signal(signal.SIGINT, kill_bots)
        try:
            # These signals are UNIX-only territory, will ValueError here on Windows
            signal.signal(signal.SIGHUP, kill_bots)
            # TODO: reload config on SIGUSR1
            # signal.signal(signal.SIGUSR1, lambda x, y: bot.do_next_tick(bot.reread_config))
        except ValueError:
            log.debug("Cannot set all signals -- not available on this platform")
        bot.run()
    except errors.NoBotsAvailable:
        sys.exit(70)  # 70= "Software error" in /usr/include/sysexts.h


def bot_job(bot, job):
    return lambda x, y: bot.do_next_tick(job)


if __name__ == '__main__':
    main()

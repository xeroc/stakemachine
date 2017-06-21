#!/usr/bin/env python3
import yaml
import logging
import click
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
from stakemachine.bot import BotInfrastructure


@click.group()
@click.option(
    "--configfile",
    default="config.yml",
)
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
def run(ctx):
    """ Continuously run the bot
    """
    bot = BotInfrastructure(ctx.config)
    bot.run()


if __name__ == '__main__':
    main()

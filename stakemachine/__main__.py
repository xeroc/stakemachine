#!/usr/bin/env python3
import json
import sys
import os
import argparse
import time
from pprint import pprint
import yaml

import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
from stakemachine import bot
log = logging.getLogger(__name__)


def replaceEnvironmentalVariables(config):
    if not isinstance(config, dict):
        return config
    else:
        for key in config:
            if isinstance(config[key], str):
                try:
                    config[key] = json.loads(config[key].format(**os.environ))
                except:
                    config[key] = config[key].format(**os.environ)
            else:
                config[key] = replaceEnvironmentalVariables(config[key])
        return config


def main() :
    global args

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Command line tool to manage trading bots for the DEX"
    )

    """
        Default settings for all tools
    """
    parser.add_argument(
        '--config', '-c',
        type=str,
        default="config.yml",
        help='Configuration python file'
    )
    parser.add_argument(
        '--verbose', '-v',
        type=int,
        default=3,
        help='Verbosity'
    )
    subparsers = parser.add_subparsers(help='sub-command help')

    once = subparsers.add_parser('once', help='Run the bot once')
    once.set_defaults(command="once")

    cont = subparsers.add_parser('run', help='Run the bot continuously')
    cont.set_defaults(command="run")

    cancel = subparsers.add_parser('cancelall', help='Run the bot continuously')
    cancel.set_defaults(command="cancelall")

    placed = subparsers.add_parser('orderplaced', help='')
    placed.set_defaults(command="orderplaced")
    placed.add_argument(
        'orderid',
        type=str,
        help=''
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    # Logging
    log = logging.getLogger("stakemachine")
    verbosity = ["critical",
                 "error",
                 "warn",
                 "info",
                 "debug"][int(min(args.verbose, 4))]
    log.setLevel(getattr(logging, verbosity.upper()))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, verbosity.upper()))
    ch.setFormatter(formatter)
    log.addHandler(ch)

    # GrapheneAPI logging
    if args.verbose > 4:
        verbosity = ["critical",
                     "error",
                     "warn",
                     "info",
                     "debug"][int(min((args.verbose - 4), 4))]
        gphlog = logging.getLogger("graphenebase")
        gphlog.setLevel(getattr(logging, verbosity.upper()))
        gphlog.addHandler(ch)
    if args.verbose > 8:
        verbosity = ["critical",
                     "error",
                     "warn",
                     "info",
                     "debug"][int(min((args.verbose - 8), 4))]
        gphlog = logging.getLogger("grapheneapi")
        gphlog.setLevel(getattr(logging, verbosity.upper()))
        gphlog.addHandler(ch)

    with open(args.config, 'r') as ymlfile:
        config = yaml.load(ymlfile)

    config = replaceEnvironmentalVariables(config)

    if isinstance(config["safe_mode"], str):
        config["safe_mode"] = config["safe_mode"].lower() in ["true", "yes", "y"]

    if "markets" not in config and "MARKETS" in os.environ:
        markets = json.loads(os.environ["MARKETS"])
        config["watch_markets"] = markets
        for name in config["bots"]:
            config["bots"][name]["markets"] = markets

    if (("wallet_host" not in config or not config["wallet_host"]) and
            ("wif" not in config or not config["wif"])):
        raise Exception(
            "Need either a wif key or connection details for to the cli wallet."
        )

    log.info("Configuration: %s" % json.dumps(config, indent=4))

    # initialize the bot infrastructure with our settings
    bot.init(config)

    if args.command == "run":
        bot.run()
    elif args.command == "once":
        bot.once()
    elif args.command == "cancelall":
        bot.cancel_all()
    elif args.command == "orderplaced":
        bot.orderplaced(args.orderid)

args = None

if __name__ == '__main__':
    main()

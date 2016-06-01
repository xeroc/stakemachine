#!/usr/bin/env python3
import json
import os
import argparse
from pprint import pprint
import yaml
from stakemachine import bot, registration
from grapheneapi.graphenewsrpc import GrapheneWebsocketRPC
from graphenebase import account
import string
import random


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
    subparsers = parser.add_subparsers(help='sub-command help')

    once = subparsers.add_parser('once', help='Run the bot once')
    once.set_defaults(command="once")

    cont = subparsers.add_parser('run', help='Run the bot continuously')
    cont.set_defaults(command="run")

    cont = subparsers.add_parser('cancelall', help='Run the bot continuously')
    cont.set_defaults(command="cancelall")

    args = parser.parse_args()

    with open(args.config, 'r') as ymlfile:
        config = yaml.load(ymlfile)

    config = replaceEnvironmentalVariables(config)

    if isinstance(config["safe_mode"], str):
        config["safe_mode"] = config["safe_mode"].lower() in ["true", "yes", "y"]

    ws = GrapheneWebsocketRPC(config.witness_url)

    if "markets" not in config and "MARKETS" in os.environ:
        markets = json.loads(os.environ["MARKETS"])
        config["watch_markets"] = markets
        for name in config["bots"]:
            config["bots"][name]["markets"] = markets

    if (("account" not in config or not config["account"]) and
            ("wif" not in config or not config["wif"])):
        raise Exception(
            "Need either an account (name) or a wif key"
        )

    elif "wif" not in config or not config["wif"]:
        print("No wif given, creating and registering %s" % config["account"])
        wif_key = registration.register_account(config["account"])
        if wif_key:
            raise Exception(
                """Generated a wif key and registered the account successfully,
                please backup the brainkey and put the WIF key in config.yml before restarting"""
            )
        else:
            raise Exception(
                "No wif key given and account creation failed."
            )

    elif "account" not in config or not config["account"]:
        print("No account name given, fetching the account name from the blockchain...")
        privateKey = account.PrivateKey(config["wif"])
        publicKey = privateKey.get_private().pubkey
        public_key = format(publicKey, "BTS")
        references = ws.get_key_references([public_key])[0]
        if len(references) > 0:
            account_id = references[0]
            account_name = ws.get_account(account_id)["name"]
            config["account"] = account_name
        else:
            print("No account name for the private key given, registering an account with a random name...")
            s = ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for c in range(16))
            random_account_name = s[:8] + '-' + s[8:]
            wif_key = registration.register_account(random_account_name, wif_key=config["wif"])
            if wif_key == config["wif"]:
                print("account %s successfully registered for private key %s" % (random_account_name, wif_key))
                config["account"] = random_account_name
            else:
                raise Exception(
                    "Account creation failed"
                )
    else:
        key_auths = ws.get_account(config["account"])["owner"]["key_auths"]
        privateKey = account.PrivateKey(config["wif"])
        publicKey = privateKey.get_private().pubkey
        public_key = format(publicKey, "BTS")

        for key in key_auths:
            if public_key == key[0]:
                print("Account name and wif key match up, continuing...")
            else:
                raise Exception(
                    "Account name and wif key don't match up, abandon all hope."
                )

    pprint(config)

    # initialize the bot infrastructure with our settings
    bot.init(config)

    if args.command == "run":
        bot.run()
    elif args.command == "once":
        bot.once()
    elif args.command == "cancelall":
        bot.cancel_all()

args = None
if __name__ == '__main__':
    main()

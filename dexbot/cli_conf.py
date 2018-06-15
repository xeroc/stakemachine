"""
A module to provide an interactive text-based tool for dexbot configuration
The result is dexbot can be run without having to hand-edit config files.
If systemd is detected it will offer to install a user service unit (under ~/.local/share/systemd
This requires a per-user systemd process to be running

Requires the 'whiptail' tool for text-based configuration (so UNIX only)
if not available, falls back to a line-based configurator ("NoWhiptail")

Note there is some common cross-UI configuration stuff: look in basestrategy.py
It's expected GUI/web interfaces will be re-implementing code in this file, but they should
understand the common code so worker strategy writers can define their configuration once
for each strategy class.
"""

import importlib
import pathlib
import os
import os.path
import sys
import re
import subprocess

from dexbot.whiptail import get_whiptail
from dexbot.basestrategy import BaseStrategy

from bitshares import BitShares

# FIXME: auto-discovery of strategies would be cool but can't figure out a way
STRATEGIES = [
    {'tag': 'relative',
     'class': 'dexbot.strategies.relative_orders',
     'name': 'Relative Orders'},
    {'tag': 'stagger',
     'class': 'dexbot.strategies.staggered_orders',
     'name': 'Staggered Orders'}]

SYSTEMD_SERVICE_NAME = os.path.expanduser(
    "~/.local/share/systemd/user/dexbot.service")

SYSTEMD_SERVICE_FILE = """
[Unit]
Description=Dexbot

[Service]
Type=notify
WorkingDirectory={homedir}
ExecStart={exe} --systemd run
TimeoutSec=20m
Environment=PYTHONUNBUFFERED=true
Environment=UNLOCK={passwd}

[Install]
WantedBy=default.target
"""


def select_choice(current, choices):
    """ For the radiolist, get us a list with the current value selected """
    return [(tag, text, (current == tag and "ON") or "OFF")
            for tag, text in choices]


def process_config_element(elem, d, config):
    """ Process an item of configuration metadata display a widget as appropriate
        d: the Dialog object
        config: the config dictionary for this worker
    """
    if elem.type == "string":
        txt = d.prompt(elem.description, config.get(elem.key, elem.default))
        if elem.extra:
            while not re.match(elem.extra, txt):
                d.alert("The value is not valid")
                txt = d.prompt(
                    elem.description, config.get(
                        elem.key, elem.default))
        config[elem.key] = txt
    if elem.type == "bool":
        value = config.get(elem.key, elem.default)
        value = 'yes' if value else 'no'
        config[elem.key] = d.confirm(elem.description, value)
    if elem.type in ("float", "int"):
        txt = d.prompt(elem.description, str(config.get(elem.key, elem.default)))
        while True:
            try:
                if elem.type == "int":
                    val = int(txt)
                else:
                    val = float(txt)
                if val < elem.extra[0]:
                    d.alert("The value is too low")
                elif elem.extra[1] and val > elem.extra[1]:
                    d.alert("the value is too high")
                else:
                    break
            except ValueError:
                d.alert("Not a valid value")
            txt = d.prompt(elem.description, str(config.get(elem.key, elem.default)))
        config[elem.key] = val
    if elem.type == "choice":
        config[elem.key] = d.radiolist(elem.description, select_choice(
            config.get(elem.key, elem.default), elem.extra))


def dexbot_service_running():
    """ Return True if dexbot service is running
    """
    cmd = 'systemctl --user status dexbot'
    output = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    for line in output.stdout.readlines():
        if b'Active:' in line and b'(running)' in line:
            return True
    return False


def setup_systemd(d, config):
    if not os.path.exists("/etc/systemd"):
        return  # No working systemd

    if not d.confirm(
            "Do you want to run dexbot as a background (daemon) process?"):
        config['systemd_status'] = 'disabled'
        return

    redo_setup = False
    if os.path.exists(SYSTEMD_SERVICE_NAME):
        redo_setup = d.confirm('Redo systemd setup?', 'no')

    if not os.path.exists(SYSTEMD_SERVICE_NAME) or redo_setup:
        path = '~/.local/share/systemd/user'
        path = os.path.expanduser(path)
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)
        password = d.prompt(
            "The wallet password\n"
            "NOTE: this will be saved on disc so the worker can run unattended. "
            "This means anyone with access to this computer's files can spend all your money",
            password=True)

        # Because we hold password be restrictive
        fd = os.open(SYSTEMD_SERVICE_NAME, os.O_WRONLY | os.O_CREAT, 0o600)
        with open(fd, "w") as fp:
            fp.write(
                SYSTEMD_SERVICE_FILE.format(
                    exe=sys.argv[0],
                    passwd=password,
                    homedir=os.path.expanduser("~")))
        # The dexbot service file was edited, reload the daemon configs
        os.system('systemctl --user daemon-reload')

    # Signal cli.py to set the unit up after writing config file
    config['systemd_status'] = 'enabled'


def configure_worker(d, worker):
    default_strategy = worker.get('module', 'dexbot.strategies.relative_orders')
    for i in STRATEGIES:
        if default_strategy == i['class']:
            default_strategy = i['tag']

    worker['module'] = d.radiolist(
        "Choose a worker strategy", select_choice(
            default_strategy, [(i['tag'], i['name']) for i in STRATEGIES]))
    for i in STRATEGIES:
        if i['tag'] == worker['module']:
            worker['module'] = i['class']
    # Import the worker class but we don't __init__ it here
    strategy_class = getattr(
        importlib.import_module(worker["module"]),
        'Strategy'
    )
    # Use class metadata for per-worker configuration
    configs = strategy_class.configure()
    if configs:
        for c in configs:
            process_config_element(c, d, worker)
    else:
        d.alert("This worker type does not have configuration information. "
                "You will have to check the worker code and add configuration values to config.yml if required")
    return worker


def configure_dexbot(config):
    d = get_whiptail()
    workers = config.get('workers', {})
    if not workers:
        while True:
            txt = d.prompt("Your name for the worker")
            config['workers'] = {txt: configure_worker(d, {})}
            if not d.confirm("Set up another worker?\n(DEXBot can run multiple workers in one instance)"):
                break
        setup_systemd(d, config)
    else:
        action = d.menu("You have an existing configuration.\nSelect an action:",
                        [('NEW', 'Create a new worker'),
                         ('DEL', 'Delete a worker'),
                         ('EDIT', 'Edit a worker'),
                         ('CONF', 'Redo general config')])
        if action == 'EDIT':
            worker_name = d.menu("Select worker to edit", [(i, i) for i in workers])
            config['workers'][worker_name] = configure_worker(d, config['workers'][worker_name])
            bitshares_instance = BitShares(config['node'])
            strategy = BaseStrategy(worker_name, bitshares_instance=bitshares_instance)
            strategy.purge()
        elif action == 'DEL':
            worker_name = d.menu("Select worker to delete", [(i, i) for i in workers])
            del config['workers'][worker_name]
            bitshares_instance = BitShares(config['node'])
            strategy = BaseStrategy(worker_name, bitshares_instance=bitshares_instance)
            strategy.purge()
        elif action == 'NEW':
            txt = d.prompt("Your name for the new worker")
            config['workers'][txt] = configure_worker(d, {})
        elif action == 'CONF':
            config['node'] = d.prompt("BitShares node to use", default=config['node'])
            setup_systemd(d, config)
    d.clear()
    return config

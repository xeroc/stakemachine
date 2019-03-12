import re

from dexbot.whiptail import get_whiptail

import bitshares
from bitshares.instance import shared_bitshares_instance
from bitshares.asset import Asset
from bitshares.account import Account
from bitshares.exceptions import KeyAlreadyInStoreException, AccountDoesNotExistsException
from bitsharesbase.account import PrivateKey


def select_choice(current, choices):
    """ For the radiolist, get us a list with the current value selected """
    return [(tag, text, (current == tag and "ON") or "OFF")
            for tag, text in choices]


def process_config_element(elem, whiptail, config):
    """ Process an item of configuration metadata display a widget as appropriate
        d: the Dialog object
        config: the config dictionary for this worker
    """
    if elem.description:
        title = '{} - {}'.format(elem.title, elem.description)
    else:
        title = elem.title

    if elem.type == "string":
        txt = whiptail.prompt(title, config.get(elem.key, elem.default))
        if elem.extra:
            while not re.match(elem.extra, txt):
                whiptail.alert("The value is not valid")
                txt = whiptail.prompt(
                    title, config.get(
                        elem.key, elem.default))
        config[elem.key] = txt

    if elem.type == "bool":
        value = config.get(elem.key, elem.default)
        value = 'yes' if value else 'no'
        config[elem.key] = whiptail.confirm(title, value)

    if elem.type in ("float", "int"):
        while True:
            if elem.type == 'int':
                template = '{}'
            else:
                template = '{:.8f}'
            txt = whiptail.prompt(title, template.format(config.get(elem.key, elem.default)))
            try:
                if elem.type == "int":
                    val = int(txt)
                else:
                    val = float(txt)
                if val < elem.extra[0]:
                    whiptail.alert("The value is too low")
                elif elem.extra[1] and val > elem.extra[1]:
                    whiptail.alert("the value is too high")
                else:
                    break
            except ValueError:
                whiptail.alert("Not a valid value")
        config[elem.key] = val

    if elem.type == "choice":
        config[elem.key] = whiptail.radiolist(title, select_choice(
            config.get(elem.key, elem.default), elem.extra))

        
class ConfigValidator:
    """ validation methods borrowed from gui WorkerController for Cli
    """

    def __init__(self, whiptail, bitshares_instance):
        self.bitshares = bitshares_instance or shared_bitshares_instance()
        self.whiptail = whiptail

    @classmethod
    def validate_worker_name(cls, worker_name, old_worker_name=None):
        if old_worker_name != worker_name:
            worker_names = Config().workers_data.keys()
            # Check that the name is unique
            if worker_name in worker_names:
                return False
            return True
        return True
        
    def validate_asset(self, asset):
        try:
            Asset(asset, bitshares_instance=self.bitshares)
            return True
        except bitshares.exceptions.AssetDoesNotExistsException:
            return False

    def validate_account_name(self, account):
        if not account:
            return False
        try:
            Account(account, bitshares_instance=self.bitshares)
            return True
        except bitshares.exceptions.AccountDoesNotExistsException:
            return False

    def validate_private_key(self, account, private_key):
        wallet = self.bitshares.wallet
        if not private_key:
            # Check if the private key is already in the database
            accounts = wallet.getAccounts()
            if any(account == d['name'] for d in accounts):
                return True
            return False

        try:
            pubkey = format(PrivateKey(private_key).pubkey, self.bitshares.prefix)
        except ValueError:
            return False

        accounts = wallet.getAllAccounts(pubkey)
        account_names = [account['name'] for account in accounts]

        if account in account_names:
            return True
        else:
            return False

    def validate_private_key_type(self, account, private_key):
        account = Account(account)
        pubkey = format(PrivateKey(private_key).pubkey, self.bitshares.prefix)
        key_type = self.bitshares.wallet.getKeyType(account, pubkey)
        if key_type != 'active' and key_type != 'owner':
            return False
        return True

    def add_private_key(self, private_key):
        wallet = self.bitshares.wallet
        try:
            wallet.addPrivateKey(private_key)
        except KeyAlreadyInStoreException:
            # Private key already added
            pass
        
    def list_accounts(self):
        accounts = self.bitshares.wallet.getAccounts()
        account_list = [(i['name'], i['type']) for i in accounts]
        if len(account_list) ==  0:
            account_list = [('none', 'none')]
        return account_list
        
    def add_account(self):
        # this method modeled off of worker_controller in gui
        account = self.whiptail.prompt("Your Account Name")
        private_key = self.whiptail.prompt("Your Private Key", password=True)
                    
        if not self.validate_account_name(account):
            self.whiptail.alert("Account name does not exist.")
            return False
        if not self.validate_private_key(account, private_key):
            self.whiptail.alert("Private key is invalid")
            return False
        if private_key and not self.validate_private_key_type(account, private_key):
            self.whiptail.alert("Please use active private key.")
            return False
        
        self.add_private_key(private_key)
        self.whiptail.alert("Private Key added successfully.")
        return account


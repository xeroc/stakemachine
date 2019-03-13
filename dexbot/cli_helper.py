import bitshares
from bitshares.instance import shared_bitshares_instance
from bitshares.account import Account
from bitshares.exceptions import KeyAlreadyInStoreException
from bitsharesbase.account import PrivateKey


class ConfigValidator:
    """ validation methods borrowed from gui WorkerController for Cli
    """

    def __init__(self, whiptail, bitshares_instance):
        self.bitshares = bitshares_instance or shared_bitshares_instance()
        self.whiptail = whiptail

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
        if len(account_list) == 0:
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

    def del_account(self):
        # Todo: implement in the cli_conf
        # account = self.whiptail.prompt("Account Name")
        public_key = self.whiptail.prompt("Public Key", password=True)
        wallet = self.bitshares.wallet
        try:
            wallet.removePrivateKeyFromPublicKey(public_key)
        except Exception:
            pass

import bitshares


class WalletController:
    def __init__(self, bitshares_instance):
        self.bitshares = bitshares_instance

    def wallet_created(self):
        return self.bitshares.wallet.created()

    def create_wallet(self, password, confirm_password):
        if password == confirm_password:
            self.bitshares.wallet.create(password)
            return True
        else:
            return False

    def unlock_wallet(self, password):
        try:
            self.bitshares.wallet.unlock(password)
            return True
        except bitshares.exceptions.WrongMasterPasswordException:
            return False

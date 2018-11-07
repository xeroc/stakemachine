import sys

from dexbot.config import Config
from dexbot.controllers.main_controller import MainController
from dexbot.controllers.wallet_controller import WalletController
from dexbot.views.create_wallet import CreateWalletView
from dexbot.views.unlock_wallet import UnlockWalletView
from dexbot.views.worker_list import MainView

from PyQt5.Qt import QApplication
from bitshares import BitShares


class App(QApplication):

    def __init__(self, sys_argv):
        super(App, self).__init__(sys_argv)

        config = Config()
        bitshares_instance = BitShares(config['node'], num_retries=-1)

        # Wallet unlock
        wallet_controller = WalletController(bitshares_instance)
        if wallet_controller.wallet_created():
            unlock_view = UnlockWalletView(wallet_controller)
        else:
            unlock_view = CreateWalletView(wallet_controller)

        if unlock_view.exec_():
            bitshares_instance = wallet_controller.bitshares
            self.main_controller = MainController(bitshares_instance, config)
            self.main_view = MainView(self.main_controller)
            self.main_view.show()
        else:
            sys.exit()


def main():
    app = App(sys.argv)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

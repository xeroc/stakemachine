from dexbot.basestrategy import BaseStrategy
from dexbot.queue.idle_queue import idle_add

from bitshares.amount import Amount


class Strategy(BaseStrategy):
    """ Staggered Orders strategy
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define Callbacks
        self.onMarketUpdate += self.check_orders
        self.onAccount += self.check_orders

        self.error_ontick = self.error
        self.error_onMarketUpdate = self.error
        self.error_onAccount = self.error

        self.worker_name = kwargs.get('name')
        self.view = kwargs.get('view')

        self.check_orders()

    def error(self, *args, **kwargs):
        self.cancel_all()
        self.disabled = True
        self.log.info(self.execute())

    def update_orders(self):
        self.log.info('Change detected, updating orders')
        # Todo: implement logic

    def check_orders(self, *args, **kwargs):
        """ Tests if the orders need updating
        """
        pass
        # Todo: implement logic

    # GUI updaters
    def update_gui_profit(self):
        pass

    def update_gui_slider(self):
        pass

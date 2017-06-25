from stakemachine.basestrategy import BaseStrategy
import logging
log = logging.getLogger(__name__)


class Walls(BaseStrategy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define Callbacks
        self.onMarketUpdate += self.update
        self.ontick += self.tick

    def update(self, d):
        pass

    def tick(self, d):
        print(self.orders)
        print(self.market.ticker())

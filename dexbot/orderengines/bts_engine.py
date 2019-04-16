from bitshares.instance import shared_bitshares_instance


class OrderEngine:

    def __init__(self,
                 bitshares_instance=None):
        
        # BitShares instance
        self.bitshares = bitshares_instance or shared_bitshares_instance()

        # Dex instance used to get different fees for the market
        self.dex = Dex(self.bitshares)


*********************
How to Deploy the Bot
*********************

.. warning:: None of what is stated in the documentation is to be
             interpreted as investment advice. You alone are responsible
             for losses caused by any of the scripts described and
             demonstrated here!

Requirements
############

1) :doc:`Installed <wallet>` `cli_wallet` with open RPC port
2) Imported (active) private key of the trading account into the `cli_wallet`::

    import_key <account-name> <wif ke>

Configuration
#############

For configuration, you need to provide

* the host that runs the wallet (with port)
* an url to an API (could be run locally as well)
* a list of all markets that should be served by the bots

The configuration of the ``safe_mode`` flag, allows to test your code in
dry-mode. If this flag is set to ``False``, the Bot will actually
produce transactions (orders, cancelation, etc..)

.. code-block:: python

    # Wallet RPC connection details
    wallet_host           = "localhost"
    wallet_port           = 8092

    # Websocket URL
    witness_url           = "ws://testnet.bitshares.eu/ws"

    # Set of ALL markets that you inted to serve
    watch_markets         = ["PEG.PARITY : TEST"]
    market_separator      = " : "  # separator between assets

    # Your account that executes the trades
    account               = "xeroc"

    # If this flag is set to True, nothing will be done really
    safe_mode             = True

    # Each bot has its individual name and carries the strategy and settings
    bots = {}

Loading and Configuration of Strategies
#######################################

Each bot needs to be loaded into the configuration file:

.. code-block:: python

    from strategies.maker import MakerRamp, MakerSellBuyWalls

And, of course, each bot comes with its own set of settings.

Executing the Bot
#################

The bot can be run in two different ways:

* ``python3 main.py``: (**single shot**) Will call the strategie-specific ``init()`` call
* ``python3 run_cont``: (**continuous mode**) Will call the strategie-specific ``init()`` call
  and continue running to react on notifiations:

  * ``tick()``: will be called on arrival of new blocks
  * ``orderFilled()``: will be called if one of the bot's orders is filled
  * ``orderPlaced()``: will be called after ``place()`` **for each** order that the strategy has placed newly

The bot will create ``.json`` files for each bot that store the
temporary data of the bot (e.g. opened orders) to be able to distinguish
bots serving the same market.

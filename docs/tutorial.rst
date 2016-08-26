*********************
How to Deploy the Bot
*********************

.. warning:: None of what is stated in the documentation is to be
             interpreted as investment advice. You alone are responsible
             for losses caused by any of the scripts described and
             demonstrated here!

Executing the Bot
#################

The bot can be run in two different ways:

* ``stakemachine once``: (**single shot**) Will call the strategie-specific ``init()`` call
* ``stakemachine run``: (**continuous mode**) Will call the strategie-specific ``init()`` call
  and continue running to react on notifiations:

  * ``tick()``: will be called on arrival of new blocks
  * ``orderFilled()``: will be called if one of the bot's orders is filled
  * ``orderPlaced()``: will be called after ``place()`` **for each** order that the strategy has placed newly

The bot will create ``.json`` files for each bot that store the
temporary data of the bot (e.g. opened orders) to be able to distinguish
bots serving the same market.

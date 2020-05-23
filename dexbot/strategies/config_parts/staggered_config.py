from dexbot.strategies.config_parts.base_config import BaseConfig, ConfigElement


class StaggeredConfig(BaseConfig):
    @classmethod
    def configure(cls, return_base_config=True):
        """
        Modes description:

        Mountain:
        - Buy orders same QUOTE
        - Sell orders same BASE

        Neutral:
        - Buy orders lower_order_base * sqrt(1 + increment)
        - Sell orders higher_order_quote * sqrt(1 + increment)

        Valley:
        - Buy orders same BASE
        - Sell orders same QUOTE

        Buy slope:
        - All orders same BASE (profit comes in QUOTE)

        Sell slope:
        - All orders same QUOTE (profit made in BASE)
        """
        modes = [
            ('mountain', 'Mountain'),
            ('neutral', 'Neutral'),
            ('valley', 'Valley'),
            ('buy_slope', 'Buy Slope'),
            ('sell_slope', 'Sell Slope'),
        ]

        return BaseConfig.configure(return_base_config) + [
            ConfigElement(
                'mode',
                'choice',
                'neutral',
                'Strategy mode',
                'How to allocate funds and profits. Doesn\'t effect existing orders, only future ones',
                modes,
            ),
            ConfigElement(
                'spread', 'float', 6, 'Spread', 'The percentage difference between buy and sell', (0, None, 2, '%')
            ),
            ConfigElement(
                'increment',
                'float',
                4,
                'Increment',
                'The percentage difference between staggered orders',
                (0, None, 2, '%'),
            ),
            ConfigElement(
                'center_price_dynamic',
                'bool',
                True,
                'Market center price',
                'Begin strategy with center price obtained from the market. Use with mature markets',
                None,
            ),
            ConfigElement(
                'center_price',
                'float',
                0,
                'Manual center price',
                'In an immature market, give a center price manually to begin with. BASE/QUOTE',
                (0, 1000000000, 8, ''),
            ),
            ConfigElement(
                'lower_bound',
                'float',
                1,
                'Lower bound',
                'The lowest price (Quote/Base) in the range',
                (0, 1000000000, 8, ''),
            ),
            ConfigElement(
                'upper_bound',
                'float',
                1000000,
                'Upper bound',
                'The highest price (Quote/Base) in the range',
                (0, 1000000000, 8, ''),
            ),
            ConfigElement(
                'instant_fill', 'bool', True, 'Allow instant fill', 'Allow to execute orders by market', None
            ),
            ConfigElement(
                'operational_depth',
                'int',
                10,
                'Operational depth',
                'Order depth to maintain on books',
                (2, 9999999, None),
            ),
            ConfigElement(
                'enable_fallback_logic',
                'bool',
                True,
                'Enable fallback logic',
                'When unable to close the spread, cancel lowest buy order and place closer buy order',
                None,
            ),
            ConfigElement(
                'enable_stop_loss',
                'bool',
                False,
                'Enable Stop Loss',
                'Stop Loss order placed when bid price comes near lower bound',
                None,
            ),
            ConfigElement(
                'stop_loss_discount',
                'float',
                5,
                'Stop Loss discount',
                'Discount percent, Stop Loss order price = bid price / (1 + discount percent)',
                (0, None, 2, '%'),
            ),
            ConfigElement(
                'stop_loss_amount',
                'float',
                50,
                'Stop Loss Amount',
                'Relative amount of QUOTE asset to sell at Stop Loss, percentage',
                (0, None, 2, '%'),
            ),
        ]

    @classmethod
    def configure_details(cls, include_default_tabs=True):
        return BaseConfig.configure_details(include_default_tabs) + []

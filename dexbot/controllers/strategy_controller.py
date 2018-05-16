from dexbot.queue.idle_queue import idle_add
from dexbot.views.errors import gui_error
from dexbot.strategies.staggered_orders import Strategy as StaggeredOrdersStrategy

from bitshares.market import Market
from bitshares.asset import AssetDoesNotExistsException


class RelativeOrdersController:

    def __init__(self, view, worker_controller, worker_data):
        self.view = view
        self.worker_controller = worker_controller
        self.view.strategy_widget.relative_order_size_checkbox.toggled.connect(
            self.onchange_relative_order_size_checkbox
        )

        if worker_data:
            self.set_config_values(worker_data)

    @gui_error
    def onchange_relative_order_size_checkbox(self, checked):
        if checked:
            self.order_size_input_to_relative()
        else:
            self.order_size_input_to_static()

    @gui_error
    def order_size_input_to_relative(self):
        self.view.strategy_widget.amount_input.setSuffix('%')
        self.view.strategy_widget.amount_input.setDecimals(2)
        self.view.strategy_widget.amount_input.setMaximum(100.00)
        self.view.strategy_widget.amount_input.setMinimumWidth(151)
        self.view.strategy_widget.amount_input.setValue(10.00)

    @gui_error
    def order_size_input_to_static(self):
        self.view.strategy_widget.amount_input.setSuffix('')
        self.view.strategy_widget.amount_input.setDecimals(8)
        self.view.strategy_widget.amount_input.setMaximum(1000000000.000000)
        self.view.strategy_widget.amount_input.setValue(0.000000)

    @gui_error
    def set_config_values(self, worker_data):
        if worker_data.get('amount_relative', False):
            self.order_size_input_to_relative()
            self.view.strategy_widget.relative_order_size_checkbox.setChecked(True)
        else:
            self.order_size_input_to_static()
            self.view.strategy_widget.relative_order_size_checkbox.setChecked(False)

        self.view.strategy_widget.amount_input.setValue(float(worker_data.get('amount', 0)))
        self.view.strategy_widget.center_price_input.setValue(worker_data.get('center_price', 0))
        self.view.strategy_widget.spread_input.setValue(worker_data.get('spread', 5))

        if worker_data.get('center_price_dynamic', True):
            self.view.strategy_widget.center_price_dynamic_checkbox.setChecked(True)
        else:
            self.view.strategy_widget.center_price_dynamic_checkbox.setChecked(False)

    @property
    def values(self):
        data = {
            'amount': self.view.strategy_widget.amount_input.value(),
            'amount_relative': self.view.strategy_widget.relative_order_size_checkbox.isChecked(),
            'center_price': self.view.strategy_widget.center_price_input.value(),
            'center_price_dynamic': self.view.strategy_widget.center_price_dynamic_checkbox.isChecked(),
            'spread': self.view.strategy_widget.spread_input.value()
        }
        return data


class StaggeredOrdersController:

    def __init__(self, view, worker_controller, worker_data):
        self.view = view
        self.worker_controller = worker_controller

        if worker_data:
            self.set_config_values(worker_data)

        worker_controller.view.base_asset_input.editTextChanged.connect(lambda: self.on_value_change())
        worker_controller.view.quote_asset_input.textChanged.connect(lambda: self.on_value_change())
        widget = self.view.strategy_widget
        widget.amount_input.valueChanged.connect(lambda: self.on_value_change())
        widget.spread_input.valueChanged.connect(lambda: self.on_value_change())
        widget.increment_input.valueChanged.connect(lambda: self.on_value_change())
        widget.lower_bound_input.valueChanged.connect(lambda: self.on_value_change())
        widget.upper_bound_input.valueChanged.connect(lambda: self.on_value_change())
        self.on_value_change()

    @gui_error
    def set_config_values(self, worker_data):
        widget = self.view.strategy_widget
        widget.amount_input.setValue(worker_data.get('amount', 0))
        widget.increment_input.setValue(worker_data.get('increment', 4))
        widget.spread_input.setValue(worker_data.get('spread', 6))
        widget.lower_bound_input.setValue(worker_data.get('lower_bound', 0.000001))
        widget.upper_bound_input.setValue(worker_data.get('upper_bound', 1000000))

    @gui_error
    def on_value_change(self):
        base_asset = self.worker_controller.view.base_asset_input.currentText()
        quote_asset = self.worker_controller.view.quote_asset_input.text()
        try:
            market = Market('{}:{}'.format(quote_asset, base_asset))
        except AssetDoesNotExistsException:
            idle_add(self.set_required_base, 'N/A')
            idle_add(self.set_required_quote, 'N/A')
            return

        amount = self.view.strategy_widget.amount_input.value()
        spread = self.view.strategy_widget.spread_input.value() / 100
        increment = self.view.strategy_widget.increment_input.value() / 100
        lower_bound = self.view.strategy_widget.lower_bound_input.value()
        upper_bound = self.view.strategy_widget.upper_bound_input.value()

        if not (market or amount or spread or increment or lower_bound or upper_bound):
            idle_add(self.set_required_base, 'N/A')
            idle_add(self.set_required_quote, 'N/A')
            return

        strategy = StaggeredOrdersStrategy
        result = strategy.get_required_assets(market, amount, spread, increment, lower_bound, upper_bound)
        if not result:
            idle_add(self.set_required_base, 'N/A')
            idle_add(self.set_required_quote, 'N/A')
            return

        base, quote = result
        text = '{:.8f} {}'.format(base, base_asset)
        idle_add(self.set_required_base, text)
        text = '{:.8f} {}'.format(quote, quote_asset)
        idle_add(self.set_required_quote, text)

    def set_required_base(self, text):
        self.view.strategy_widget.required_base_text.setText(text)

    def set_required_quote(self, text):
        self.view.strategy_widget.required_quote_text.setText(text)

    @property
    def values(self):
        data = {
            'amount': self.view.strategy_widget.amount_input.value(),
            'spread': self.view.strategy_widget.spread_input.value(),
            'increment': self.view.strategy_widget.increment_input.value(),
            'lower_bound': self.view.strategy_widget.lower_bound_input.value(),
            'upper_bound': self.view.strategy_widget.upper_bound_input.value()
        }
        return data

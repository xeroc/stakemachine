import collections

from dexbot.views.errors import gui_error


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
        self.view.strategy_widget.manual_offset_input.setValue(worker_data.get('manual_offset', 0))

        if worker_data.get('center_price_dynamic', True):
            self.view.strategy_widget.center_price_dynamic_checkbox.setChecked(True)
        else:
            self.view.strategy_widget.center_price_dynamic_checkbox.setChecked(False)
            self.view.strategy_widget.center_price_input.setDisabled(False)

        if worker_data.get('center_price_offset', True):
            self.view.strategy_widget.center_price_offset_checkbox.setChecked(True)
        else:
            self.view.strategy_widget.center_price_offset_checkbox.setChecked(False)

    def validation_errors(self):
        error_texts = []
        if not self.view.strategy_widget.amount_input.value():
            error_texts.append("Amount can't be 0")
        if not self.view.strategy_widget.spread_input.value():
            error_texts.append("Spread can't be 0")
        return error_texts

    @property
    def values(self):
        data = {
            'amount': self.view.strategy_widget.amount_input.value(),
            'amount_relative': self.view.strategy_widget.relative_order_size_checkbox.isChecked(),
            'center_price': self.view.strategy_widget.center_price_input.value(),
            'center_price_dynamic': self.view.strategy_widget.center_price_dynamic_checkbox.isChecked(),
            'center_price_offset': self.view.strategy_widget.center_price_offset_checkbox.isChecked(),
            'spread': self.view.strategy_widget.spread_input.value(),
            'manual_offset': self.view.strategy_widget.manual_offset_input.value()
        }
        return data


class StaggeredOrdersController:

    def __init__(self, view, worker_controller, worker_data):
        self.view = view
        self.worker_controller = worker_controller

        if view:
            modes = self.strategy_modes
            for strategy_mode in modes:
                self.view.strategy_widget.mode_input.addItem(modes[strategy_mode], strategy_mode)

        if worker_data:
            self.set_config_values(worker_data)

    @gui_error
    def set_config_values(self, worker_data):
        widget = self.view.strategy_widget

        # Set strategy mode
        index = widget.mode_input.findData(self.worker_controller.get_strategy_mode(worker_data))
        widget.mode_input.setCurrentIndex(index)

        widget.increment_input.setValue(worker_data.get('increment', 4))
        widget.spread_input.setValue(worker_data.get('spread', 6))
        widget.lower_bound_input.setValue(worker_data.get('lower_bound', 0.000001))
        widget.upper_bound_input.setValue(worker_data.get('upper_bound', 1000000))

        self.view.strategy_widget.center_price_input.setValue(worker_data.get('center_price', 0))

        if worker_data.get('center_price_dynamic', True):
            self.view.strategy_widget.center_price_dynamic_checkbox.setChecked(True)
        else:
            self.view.strategy_widget.center_price_dynamic_checkbox.setChecked(False)
            self.view.strategy_widget.center_price_input.setDisabled(False)

        # Set allow instant order fill
        self.view.strategy_widget.allow_instant_fill_checkbox.setChecked(worker_data.get('allow_instant_fill', True))

    def set_required_base(self, text):
        self.view.strategy_widget.required_base_text.setText(text)

    def set_required_quote(self, text):
        self.view.strategy_widget.required_quote_text.setText(text)

    def validation_errors(self):
        error_texts = []
        if not self.view.strategy_widget.spread_input.value():
            error_texts.append("Spread can't be 0")
        if not self.view.strategy_widget.increment_input.value():
            error_texts.append("Increment can't be 0")
        if not self.view.strategy_widget.lower_bound_input.value():
            error_texts.append("Lower bound can't be 0")
        return error_texts

    @property
    def values(self):
        data = {
            'mode': self.view.strategy_widget.mode_input.currentData(),
            'spread': self.view.strategy_widget.spread_input.value(),
            'center_price': self.view.strategy_widget.center_price_input.value(),
            'center_price_dynamic': self.view.strategy_widget.center_price_dynamic_checkbox.isChecked(),
            'increment': self.view.strategy_widget.increment_input.value(),
            'lower_bound': self.view.strategy_widget.lower_bound_input.value(),
            'upper_bound': self.view.strategy_widget.upper_bound_input.value(),
            'allow_instant_fill': self.view.strategy_widget.allow_instant_fill_checkbox.isChecked()
        }
        return data

    @property
    def strategy_modes(self):
        # Todo: Activate rest of the modes once the logic is done
        modes = collections.OrderedDict()

        # modes['neutral'] = 'Neutral'
        modes['mountain'] = 'Mountain'
        # modes['valley'] = 'Valley'
        # modes['buy_slope'] = 'Buy Slope'
        # modes['sell_slope'] = 'Sell Slope'

        return modes

    @classmethod
    def strategy_modes_tuples(cls):
        modes = cls(None, None, None).strategy_modes
        return [(key, value) for key, value in modes.items()]

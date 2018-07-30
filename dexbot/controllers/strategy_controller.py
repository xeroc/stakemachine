import collections

from dexbot.qt_queue.idle_queue import idle_add
from dexbot.views.errors import gui_error
from dexbot.strategies.staggered_orders import Strategy as StaggeredOrdersStrategy

from bitshares.market import Market
from bitshares.asset import AssetDoesNotExistsException
from PyQt5 import QtWidgets


class StrategyController:
    """ Parent controller for strategies that don't have a custom controller
    """

    def __init__(self, view, configure, worker_controller, worker_data):
        self.view = view
        self.configure = configure
        self.worker_controller = worker_controller

        self.set_values(configure, worker_data)

    def validation_errors(self):
        return []

    def set_values(self, configure, worker_config):
        for option in configure:
            if worker_config and worker_config.get(option.key) is not None:
                value = worker_config[option.key]
            else:
                value = option.default

            element = self.elements[option.key]
            if not element:
                continue

            if option.type in ('int', 'float', 'string'):
                element.setValue(value)
            if option.type == 'bool':
                if value:
                    element.setChecked(True)
                else:
                    element.setChecked(False)
            if option.type == 'choice':
                # Fill the combobox
                for tag, label in option.extra:
                    element.addItem(label, tag)
                # Set the value
                index = element.findData(value)
                element.setCurrentIndex(index)

    @property
    def values(self):
        data = {}
        for key, element in self.elements.items():
            class_name = element.__class__.__name__
            if class_name in ('QDoubleSpinBox', 'QSpinBox', 'QLineEdit'):
                data[key] = element.value()
            elif class_name == 'QCheckBox':
                data[key] = element.isChecked()
            elif class_name == 'QComboBox':
                data[key] = element.currentData()
        return data

    @property
    def elements(self):
        """ Use ConfigElement of the strategy to find the elements
        """
        elements = {}
        types = (
            QtWidgets.QDoubleSpinBox,
            QtWidgets.QSpinBox,
            QtWidgets.QLineEdit,
            QtWidgets.QCheckBox,
            QtWidgets.QComboBox
        )

        for option in self.configure:
            element_name = ''.join([option.key, '_input'])
            elements[option.key] = self.view.findChild(types, element_name)
        return elements


class RelativeOrdersController(StrategyController):

    def __init__(self, view, configure, worker_controller, worker_data):
        self.view = view
        self.configure = configure
        self.worker_controller = worker_controller
        self.view.strategy_widget.relative_order_size_input.toggled.connect(
            self.onchange_relative_order_size_input
        )

        # Do this after the event connecting
        super().__init__(view, configure, worker_controller, worker_data)

        if not self.view.strategy_widget.center_price_dynamic_input.isChecked():
            self.view.strategy_widget.center_price_input.setDisabled(False)

    def onchange_relative_order_size_input(self, checked):
        if checked:
            self.order_size_input_to_relative()
        else:
            self.order_size_input_to_static()

    def order_size_input_to_relative(self):
        self.view.strategy_widget.amount_input.setSuffix('%')
        self.view.strategy_widget.amount_input.setDecimals(2)
        self.view.strategy_widget.amount_input.setMaximum(100.00)
        self.view.strategy_widget.amount_input.setMinimumWidth(170)
        self.view.strategy_widget.amount_input.setValue(10.00)

    def order_size_input_to_static(self):
        self.view.strategy_widget.amount_input.setSuffix('')
        self.view.strategy_widget.amount_input.setDecimals(8)
        self.view.strategy_widget.amount_input.setMaximum(1000000000.000000)
        self.view.strategy_widget.amount_input.setValue(0.000000)

    def validation_errors(self):
        error_texts = []
        if not self.view.strategy_widget.amount_input.value():
            error_texts.append("Order size can't be 0")
        if not self.view.strategy_widget.spread_input.value():
            error_texts.append("Spread can't be 0")
        return error_texts


class StaggeredOrdersController(StrategyController):

    def __init__(self, view, configure, worker_controller, worker_data):
        self.view = view
        self.configure = configure
        self.worker_controller = worker_controller

        if view:
            modes = self.strategy_modes
            for strategy_mode in modes:
                self.view.strategy_widget.mode_input.addItem(modes[strategy_mode], strategy_mode)

        # Do this after the event connecting
        super().__init__(view, configure, worker_controller, worker_data)

        if not self.view.strategy_widget.center_price_dynamic_input.isChecked():
            self.view.strategy_widget.center_price_input.setDisabled(False)

        # Set allow instant order fill
        self.view.strategy_widget.allow_instant_fill_checkbox.setChecked(worker_data.get('allow_instant_fill', True))

    def set_required_base(self, text):
        self.view.strategy_widget.required_base_text.setText(text)

    def set_required_quote(self, text):
        self.view.strategy_widget.required_quote_text.setText(text)

    def validation_errors(self):
        error_texts = []
        if not self.view.strategy_widget.amount_input.value():
            error_texts.append("Order size can't be 0")
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

import collections

from dexbot.views.errors import gui_error

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

            element = self.elements.get(option.key)
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
            element = self.view.findChild(types, element_name)
            if element:
                elements[option.key] = element
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
            if not self.view.strategy_widget.center_price_dynamic_input.isChecked():
                self.view.strategy_widget.center_price_input.setDisabled(False)

        # Do this after the event connecting
        super().__init__(view, configure, worker_controller, worker_data)

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

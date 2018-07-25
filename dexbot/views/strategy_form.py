import importlib

import dexbot.controllers.strategy_controller
from dexbot.views.auto_strategy_form import AutoStrategyFormWidget

from PyQt5 import QtWidgets


class StrategyFormWidget(QtWidgets.QWidget):

    def __init__(self, controller, strategy_module, config=None):
        super().__init__()
        self.controller = controller
        self.module_name = strategy_module.split('.')[-1]

        form_module = controller.strategies[strategy_module]['form_module']
        try:
            widget = getattr(
                importlib.import_module(form_module),
                'Ui_Form'
            )
            self.strategy_widget = widget()
            self.strategy_widget.setupUi(self)
        except (ValueError, AttributeError):
            self.strategy_widget = AutoStrategyFormWidget(self, strategy_module, config)

        # Assemble the controller class name
        parts = self.module_name.split('_')
        class_name = ''.join(map(str.capitalize, parts))
        class_name = class_name + 'Controller'

        try:
            # Try to get the controller
            strategy_controller = getattr(
                dexbot.controllers.strategy_controller,
                class_name
            )
        except AttributeError:
            # The controller doesn't exist, use the default controller
            strategy_controller = getattr(
                dexbot.controllers.strategy_controller,
                'StrategyController'
            )

        self.strategy_controller = strategy_controller(self, controller, config)

    @property
    def values(self):
        """ Returns values all the form values based on selected strategy
        """
        return self.strategy_controller.values

# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dexbot/views/orig/create_bot_window.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(400, 300)
        Dialog.setModal(True)
        self.gridLayout = QtWidgets.QGridLayout(Dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.widget = QtWidgets.QWidget(Dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.widget.sizePolicy().hasHeightForWidth())
        self.widget.setSizePolicy(sizePolicy)
        self.widget.setObjectName("widget")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.widget)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem = QtWidgets.QSpacerItem(179, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.cancel_button = QtWidgets.QPushButton(self.widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cancel_button.sizePolicy().hasHeightForWidth())
        self.cancel_button.setSizePolicy(sizePolicy)
        self.cancel_button.setObjectName("cancel_button")
        self.horizontalLayout_2.addWidget(self.cancel_button)
        self.save_button = QtWidgets.QPushButton(self.widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.save_button.sizePolicy().hasHeightForWidth())
        self.save_button.setSizePolicy(sizePolicy)
        self.save_button.setObjectName("save_button")
        self.horizontalLayout_2.addWidget(self.save_button)
        self.gridLayout.addWidget(self.widget, 1, 0, 1, 1)
        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")
        self.strategy_label = QtWidgets.QLabel(Dialog)
        self.strategy_label.setObjectName("strategy_label")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.strategy_label)
        self.strategy_input = QtWidgets.QComboBox(Dialog)
        self.strategy_input.setObjectName("strategy_input")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.strategy_input)
        self.account_label = QtWidgets.QLabel(Dialog)
        self.account_label.setObjectName("account_label")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.account_label)
        self.account_input = QtWidgets.QLineEdit(Dialog)
        self.account_input.setObjectName("account_input")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.account_input)
        self.botname_label = QtWidgets.QLabel(Dialog)
        self.botname_label.setObjectName("botname_label")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.botname_label)
        self.botname_input = QtWidgets.QLineEdit(Dialog)
        self.botname_input.setObjectName("botname_input")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.botname_input)
        self.gridLayout.addLayout(self.formLayout, 0, 0, 1, 1)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Create Bot"))
        self.cancel_button.setText(_translate("Dialog", "Cancel"))
        self.save_button.setText(_translate("Dialog", "Save"))
        self.strategy_label.setText(_translate("Dialog", "Strategy"))
        self.account_label.setText(_translate("Dialog", "Account"))
        self.botname_label.setText(_translate("Dialog", "Bot name"))


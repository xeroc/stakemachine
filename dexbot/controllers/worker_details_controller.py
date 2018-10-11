import csv

from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtGui import QTextCursor


class WorkerDetailsController:

    def __init__(self, view, worker_name, config):
        """ Initializes controller

            :param view: WorkerDetailsView
            :param worker_name: Worker's name
            :param config: Worker's config
        """
        self.view = view
        self.worker_name = worker_name
        self.config = config

    def initialize_worker_data(self):
        """ Initializes details view with worker's data

        """
        # Worker information
        self.view.worker_name.setText(self.worker_name)
        self.view.worker_account.setText(self.config.get('account'))

        # Common strategy information
        self.view.strategy_name.setText(self.config.get('module'))
        self.view.market.setText(self.config.get('market'))
        self.view.fee_asset.setText(self.config.get('fee_asset'))

    @staticmethod
    def populate_table_from_csv(table, file, delimiter=';', first_item_header=True):
        try:
            with open(file, 'r') as csv_file:
                file_reader = csv.reader(csv_file, delimiter=delimiter)
                rows = list(file_reader)
        except FileNotFoundError:
            print('File {} not found'.format(file))

        table.setColumnCount(len(rows[0]))

        # Set headers
        if first_item_header:
            headers = rows.pop(0)
            for header_index, header in enumerate(headers):
                item = QTableWidgetItem()
                item.setText(header)
                table.setHorizontalHeaderItem(header_index, item)

        # Set rows data
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, column in enumerate(row):
                item = QTableWidgetItem()
                item.setText(column)
                table.setItem(row_index, column_index, item)

        return table

    @staticmethod
    def populate_text_from_file(tab, file):
        try:
            tab.text.setPlainText(open(file).read())
            tab.text.moveCursor(QTextCursor.End)

            return tab
        except FileNotFoundError:
            tab.status_label.setText('File \'{}\' not found'.format(file))

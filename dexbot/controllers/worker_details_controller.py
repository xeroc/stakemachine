

class WorkerDetailsController:

    def __init__(self, view, worker_name, config):
        """ Initializes controller

            :param view: WorkerDetailsView
            :param worker_name: Worker's name
            :param config: Worker's config
        """
        self.view = view
        self.worker_name = worker_name
        self.config = config['workers'].get(self.worker_name)

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

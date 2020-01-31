from datetime import datetime, timedelta
from functools import wraps


def check_last_run(func):
    """ This decorator is intended to be used for control maintain_strategy() execution. It requires self.last_check and
        self.check_interval to be set in calling class.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start = datetime.now()
        delta = start - self.last_check

        # Don't allow to execute wrapped function if self.check_interval hasn't been passed
        if delta < timedelta(seconds=self.check_interval):
            return

        func(self, *args, **kwargs)

        self.last_check = datetime.now()
        delta = datetime.now() - start
        self.log.debug('Maintenance execution took: {:.2f} seconds'.format(delta.total_seconds()))

    return wrapper

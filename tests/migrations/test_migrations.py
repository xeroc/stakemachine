from dexbot.storage import DatabaseWorker


def test_apply_migrations(initial_db):
    DatabaseWorker.run_migrations('dexbot/migrations', 'sqlite:///{}'.format(initial_db))

"""Compatibility entry point: database.migrate now includes tenant authority."""
from database.migrate import run_migrations
from database.migration_plan import discover_authority as migration_plan

if __name__ == '__main__':
    for name in run_migrations():
        print('Applied authority-track migration: '+name)

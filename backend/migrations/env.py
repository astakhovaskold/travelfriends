from alembic import context
from sqlalchemy import create_engine, pool
from app.config import MIGRATION_DATABASE_URL
from app.db.models import metadata

config = context.config
url = config.attributes.get('database_url', MIGRATION_DATABASE_URL)
if context.is_offline_mode():
    context.configure(url=url,target_metadata=metadata,literal_binds=True,dialect_opts={'paramstyle':'named'})
    with context.begin_transaction(): context.run_migrations()
else:
    connection = config.attributes.get('connection')
    if connection is not None:
        context.configure(connection=connection,target_metadata=metadata)
        with context.begin_transaction(): context.run_migrations()
    else:
        engine = create_engine(url,poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(connection=connection,target_metadata=metadata)
            with context.begin_transaction(): context.run_migrations()

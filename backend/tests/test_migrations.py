from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, insert, select, text
from app.db.models import metadata, users, trips, messages
from scripts.import_sqlite import import_sqlite


def migration_config():
    return Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))


def test_alembic_matches_models_and_roundtrip(api):
    _,m=api
    # This test uses its own empty schema/database, established by the fixture.
    cfg=migration_config()
    with m.engine.begin() as conn:
        cfg.attributes['connection']=conn
        command.downgrade(cfg,'base')
        command.upgrade(cfg,'head')
        assert compare_metadata(MigrationContext.configure(conn),metadata)==[]
        command.downgrade(cfg,'base')
        command.upgrade(cfg,'head')
        assert conn.execute(text('select version_num from alembic_version')).scalar_one()=='0001'


def test_sqlite_import_preserves_ids_and_sequences(api,tmp_path):
    _,m=api
    with m.engine.begin() as conn:
        for table in reversed(metadata.sorted_tables): conn.execute(table.delete())
    source_path=tmp_path/'backup.db'; source_engine=create_engine('sqlite:///'+str(source_path))
    metadata.create_all(source_engine)
    with source_engine.begin() as conn:
        conn.execute(insert(users).values(id=1001,name='Existing user',registered=1,birth='1990-01-01'))
        conn.execute(insert(trips).values(id=501,user_id=1001,dest='Paris',created=100))
        conn.execute(insert(messages).values(id=701,trip_id=501,user_id=0,text='join:Existing user',created=100))
    source_engine.dispose()
    counts=import_sqlite(source_path,m.engine)
    assert counts['users']==1 and counts['messages']==1
    with m.engine.begin() as conn:
        assert conn.execute(select(users.c.name).where(users.c.id==1001)).scalar_one()=='Existing user'
        assert conn.execute(text("select subject from auth_identities where user_id=1001")).scalar_one()=='1001'
        new_id=conn.execute(insert(users).values(name='New user').returning(users.c.id)).scalar_one()
        assert new_id>1001
    with pytest.raises(ValueError,match='not empty'): import_sqlite(source_path,m.engine)


def test_legacy_orphan_preflight_is_actionable_and_atomic(api,tmp_path):
    import sqlite3
    _,m=api
    with m.engine.begin() as conn:
        for table in reversed(metadata.sorted_tables): conn.execute(table.delete())
    source=tmp_path/'legacy.db'
    # Minimal authentic legacy schema: no FK declarations (unlike new metadata).
    with sqlite3.connect(source) as conn:
        conn.executescript('''
        create table users(id integer primary key,name text);
        create table trips(id integer primary key,user_id integer);
        create table joins(trip_id integer,user_id integer);
        create table messages(id integer primary key,trip_id integer,user_id integer);
        create table reports(msg_id integer,reporter integer);
        create table reviews(id integer primary key,trip_id integer,from_id integer,to_id integer);
        create table blocks(user_id integer,blocked_id integer);
        create table kicked(trip_id integer,user_id integer);
        create table requests(trip_id integer,user_id integer);
        create table reactions(msg_id integer,user_id integer);
        insert into users values(101,'Owner');
        insert into blocks values(101,999);
        ''')
    with pytest.raises(ValueError,match=r'blocks.blocked_id.*999'):
        import_sqlite(source,m.engine)
    with m.engine.connect() as conn: assert conn.execute(select(users)).first() is None

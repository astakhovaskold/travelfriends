"""Transaction boundary plus a small SQLAlchemy text-query adapter for legacy queries.

SQL and bind parameters are portable; every context commits or rolls back AND
closes its connection. No SQLite SQL rewriting is performed here.
"""
import re
from collections.abc import Mapping
from contextlib import contextmanager
from functools import lru_cache
from sqlalchemy import create_engine, text, event
from app.config import DATABASE_URL

def get_engine(url=None):
    return _create_engine(url or DATABASE_URL)

@lru_cache(maxsize=8)
def _create_engine(url):
    engine = create_engine(url, pool_pre_ping=True, **({'connect_args': {'check_same_thread':False, 'timeout':30}} if url.startswith('sqlite') else {}))
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine,'connect')
        def configure(conn, _):
            conn.execute('PRAGMA foreign_keys=ON')
    return engine

class Row(Mapping):
    def __init__(self, row): self.data = dict(row._mapping)
    def __getitem__(self,key): return list(self.data.values())[key] if isinstance(key,int) else self.data[key]
    def __iter__(self): return iter(self.data)
    def __len__(self): return len(self.data)

class Result:
    def __init__(self,result):
        self.rows = [Row(r) for r in result] if result.returns_rows else []
        self.index = 0
    def fetchone(self):
        if self.index >= len(self.rows): return None
        row = self.rows[self.index]; self.index += 1; return row
    def fetchall(self):
        rows = self.rows[self.index:]; self.index = len(self.rows); return rows
    def __iter__(self): return iter(self.fetchall())

class Transaction:
    def __init__(self,connection): self.connection = connection
    def execute(self,sql,params=()):
        if not isinstance(params,dict):
            params = {f'p{i}':v for i,v in enumerate(params)}
            counter = iter(range(len(params)))
            sql = re.sub(r'\?',lambda _: ':p'+str(next(counter)),sql)
        return Result(self.connection.execute(text(sql),params))
    def lock_trip(self,trip_id):
        if self.connection.dialect.name == 'postgresql':
            self.execute('select id from trips where id=? for update',(trip_id,))
    def lock_user(self,user_id):
        if self.connection.dialect.name == 'postgresql':
            self.execute('select id from users where id=? for update',(user_id,))

@contextmanager
def db(url=None, *, write=False):
    engine = get_engine(url)
    with engine.connect() as connection:
        if write and engine.dialect.name == 'sqlite': connection.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            yield Transaction(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

def age_expression(column):
    if get_engine().dialect.name == 'postgresql':
        return f"cast(floor(extract(epoch from (CURRENT_TIMESTAMP - cast(nullif({column},'') as timestamp))) / 31557600) as integer)"
    return f"cast((julianday('now')-julianday({column}))/365.25 as int)"

def expiry_expression():
    if get_engine().dialect.name == 'postgresql':
        fallback = "to_char(to_timestamp(t.created) + interval '30 days', 'YYYY-MM-DD')"
    else: fallback = "date(t.created,'unixepoch','+30 days')"
    return f"coalesce(nullif(t.date_to,''), nullif(t.date_from,''), {fallback})"

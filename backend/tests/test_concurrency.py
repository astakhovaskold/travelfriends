from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from conftest import signed


def test_last_seat_is_atomic(api, ready, trip):
    c,m=api
    if m.engine.dialect.name!='postgresql': pytest.skip('PostgreSQL row lock integration test')
    tid=trip(people=1); h1=ready(202); h2=ready(303); barrier=Barrier(2)
    def join(h):
        barrier.wait(timeout=10)
        return c.post(f'/api/trips/{tid}/join',headers=h)
    with ThreadPoolExecutor(2) as pool: responses=list(pool.map(join,[h1,h2]))
    assert sorted(r.status_code for r in responses)==[200,400]
    with m.db() as db: assert db.execute('select count(*) from joins where trip_id=?',(tid,)).fetchone()[0]==1


def test_accept_and_direct_join_share_capacity_lock(api, ready, trip):
    c,m=api
    if m.engine.dialect.name!='postgresql': pytest.skip('PostgreSQL row lock integration test')
    tid=trip(approval=1,people=1); h1=ready(202); h2=ready(303)
    c.post(f'/api/trips/{tid}/join',headers=h1)
    with m.db() as db: db.execute('update trips set approval=0 where id=?',(tid,))
    barrier=Barrier(2)
    def action(mode):
        barrier.wait(timeout=10)
        return c.post(f'/api/trips/{tid}/requests/202/accept' if mode=='accept' else f'/api/trips/{tid}/join', headers=signed() if mode=='accept' else h2)
    with ThreadPoolExecutor(2) as pool: responses=list(pool.map(action,['accept','join']))
    assert sorted(r.status_code for r in responses)==[200,400]
    with m.db() as db: assert db.execute('select count(*) from joins where trip_id=?',(tid,)).fetchone()[0]==1

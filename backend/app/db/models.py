"""Portable SQLAlchemy Core schema. Epoch timestamps and ISO dates preserve legacy API."""
from sqlalchemy import MetaData, Table, Column, Integer, BigInteger, Text, Float, ForeignKey, UniqueConstraint, Index, text

metadata = MetaData()
ID = BigInteger().with_variant(Integer, 'sqlite')

def integer(name, default=0, **kw): return Column(name, Integer, nullable=False, server_default=text(str(default)), **kw)
def string(name, default='', **kw): return Column(name, Text, nullable=False, server_default=text("'" + default + "'"), **kw)
def uid(name): return Column(name, ID, ForeignKey('users.id'), nullable=False)
def tid(): return Column('trip_id', Integer, ForeignKey('trips.id'), nullable=False)

users = Table('users', metadata, Column('id', ID, primary_key=True, autoincrement=True), string('name'),
    Column('username', Text), string('city'), string('about'), string('lang', 'en'), integer('rules_ok'),
    Column('birth', Text), integer('registered'), integer('banned'), integer('minor'), string('gender'), string('vibe'))
trips = Table('trips', metadata, Column('id', Integer, primary_key=True), uid('user_id'), string('dest'),
    string('date_from'), string('date_to'), integer('people',1), string('budget'), string('note'), integer('boosted_until'),
    Column('created', BigInteger, nullable=False), string('audience','all'), integer('min_age'), integer('max_age'),
    integer('approval'), string('kind','flight'), string('country'), Column('lat',Float), Column('lon',Float),
    integer('chat_open'), integer('closed'), integer('prompted'))
joins = Table('joins', metadata, tid(), uid('user_id'), Column('created',BigInteger,nullable=False),
    UniqueConstraint('trip_id','user_id'))
messages = Table('messages', metadata, Column('id',Integer,primary_key=True), tid(),
    Column('user_id',ID,nullable=False), string('text'), Column('created',BigInteger,nullable=False))  # 0 = system event
reports = Table('reports',metadata,Column('msg_id',Integer,ForeignKey('messages.id'),nullable=False),
    Column('reporter',ID,ForeignKey('users.id'),nullable=False),Column('created',BigInteger,nullable=False))
reviews = Table('reviews',metadata,Column('id',Integer,primary_key=True),tid(),
    Column('from_id',ID,ForeignKey('users.id'),nullable=False), Column('to_id',ID,ForeignKey('users.id'),nullable=False),
    integer('stars'),string('tags'),string('text'),Column('created',BigInteger,nullable=False),
    UniqueConstraint('trip_id','from_id','to_id'))
blocks = Table('blocks',metadata,uid('user_id'),Column('blocked_id',ID,ForeignKey('users.id'),nullable=False),UniqueConstraint('user_id','blocked_id'))
kicked = Table('kicked',metadata,tid(),uid('user_id'),UniqueConstraint('trip_id','user_id'))
requests = Table('requests',metadata,tid(),uid('user_id'),string('status','pending'),Column('created',BigInteger,nullable=False),UniqueConstraint('trip_id','user_id'))
reactions = Table('reactions',metadata,Column('msg_id',Integer,ForeignKey('messages.id'),nullable=False),uid('user_id'),string('emoji'),UniqueConstraint('msg_id','user_id','emoji'))
auth_identities = Table('auth_identities',metadata,Column('id',Integer,primary_key=True),uid('user_id'),string('provider'),string('subject'),Column('password_hash',Text),UniqueConstraint('provider','subject'))
sessions = Table('sessions',metadata,Column('token_hash',Text,primary_key=True),uid('user_id'),Column('expires_at',BigInteger,nullable=False))
payments = Table('payments',metadata,Column('charge_id',Text,primary_key=True),tid(),uid('user_id'),integer('amount'),string('currency'),Column('created',BigInteger,nullable=False))
for table, cols in [(trips,['user_id']), (joins,['user_id']), (messages,['trip_id','id']), (reviews,['to_id']), (requests,['trip_id','status']), (auth_identities,['user_id']), (sessions,['expires_at'])]:
    Index('ix_'+table.name+'_'+'_'.join(cols), *[table.c[c] for c in cols])

auth_limits = Table('auth_limits',metadata,Column('key',Text,primary_key=True),integer('attempts'),Column('window_end',BigInteger,nullable=False))

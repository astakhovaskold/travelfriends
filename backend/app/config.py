import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(os.getenv('ENV_FILE', str(PROJECT_ROOT / '.env.local')), override=False)

def database_url(value):
    if value.startswith('postgresql://'):
        return value.replace('postgresql://', 'postgresql+psycopg://', 1)
    if value.startswith('postgres://'):
        return value.replace('postgres://', 'postgresql+psycopg://', 1)
    return value

BOT_USERNAME = os.getenv('BOT_USERNAME', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'http://localhost:8000')
BOOST_STARS = int(os.getenv('BOOST_STARS', '50'))
ADMIN_ID = int(os.getenv('ADMIN_ID', '0') or 0)
DATABASE_URL = database_url(os.getenv('DATABASE_URL', 'sqlite:///data.db'))
MIGRATION_DATABASE_URL = database_url(os.getenv('MIGRATION_DATABASE_URL', DATABASE_URL))
SESSION_TTL = int(os.getenv('SESSION_TTL', '2592000'))
FRONTEND_PATH = Path(os.getenv('FRONTEND_PATH', str(Path(__file__).resolve().parents[2] / 'frontend' / 'index.html'))).resolve()
MAX_ACTIVE = 5
TAGS = {'reliable', 'fun', 'respectful', 'organized', 'punctual', 'late', 'rude'}
KINDS = ('flight', 'train', 'road', 'hike', 'plan', 'other')
VIBES = {'early', 'nature', 'night', 'museums', 'spontaneous', 'planner', 'food', 'photo', 'active', 'chill'}
GENDERS = ('f', 'm', 'x')

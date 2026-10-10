"""Domain vocabulary and limits; these are not deployment settings."""

MAX_ACTIVE = 5
TAGS = {"reliable", "fun", "respectful", "organized", "punctual", "late", "rude"}
KINDS = ("flight", "train", "road", "hike", "plan", "other")
VIBES = {
    "early",
    "nature",
    "night",
    "museums",
    "spontaneous",
    "planner",
    "food",
    "photo",
    "active",
    "chill",
}
GENDERS = ("f", "m", "x")
REACTIONS = ("👍", "❤️", "😂", "🔥", "😮")
CITY_MAX_LENGTH = 60
ABOUT_MAX_LENGTH = 500
DEST_MAX_LENGTH = 80
BUDGET_MAX_LENGTH = 40
NOTE_MAX_LENGTH = 500
COUNTRY_MAX_LENGTH = 60
MESSAGE_MAX_LENGTH = 1000
REVIEW_MAX_LENGTH = 300
TRIP_MAX_PEOPLE = 20
TRIP_MAX_AGE = 99
PROFILE_MAX_AGE = 100
CHAT_FLOOD_WINDOW = 30
CHAT_FLOOD_LIMIT = 15
CHAT_PING_INTERVAL = 600
AUTH_REGISTER_LIMIT = 5
AUTH_LOGIN_LIMIT = 10
AUTH_LIMIT_WINDOW = 60
AUTH_LIMIT_RETENTION = 3600
PROMPT_INTERVAL = 3600
BOOST_DURATION = 7 * 86400

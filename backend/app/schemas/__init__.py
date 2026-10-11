from pydantic import BaseModel
from typing import List, Optional


class Trip(BaseModel):
    kind: str = "flight"
    country: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    dest: str
    date_from: str = ""
    date_to: str = ""
    audience: str = "all"
    min_age: int = 0
    max_age: int = 0
    approval: int = 0
    people: int = 1
    budget: str = ""
    note: str = ""


class Profile(BaseModel):
    city: str = ""
    about: str = ""
    vibe: List[str] = []


class Reg(BaseModel):
    birth: str
    gender: str = ""
    city: str = ""
    about: str = ""
    vibe: List[str] = []
    rules_accepted: bool = False


class Msg(BaseModel):
    text: str


class Review(BaseModel):
    trip_id: int
    to_id: int
    stars: int
    tags: List[str] = []
    text: str = ""


class BlockReq(BaseModel):
    user_id: int
    on: bool = True


class KickReq(BaseModel):
    user_id: int


class React(BaseModel):
    emoji: str

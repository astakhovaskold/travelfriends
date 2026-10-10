from pydantic import BaseModel, Field


class TelegramLogin(BaseModel):
    init_data: str = Field(max_length=20000)


class EmailLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class EmailRegister(EmailLogin):
    name: str = Field(min_length=1, max_length=80)

from pydantic import BaseModel


class TokenResult(BaseModel):
    access_token: str

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasicCredentials
from ..auth.basic import basic_security
from ..auth.jwt import access_security
from .token_schema import TokenResult


router = APIRouter()


@router.post("/v1/token", response_model=TokenResult)
async def get_token(credentials: HTTPBasicCredentials = Depends(basic_security)):
    if credentials.username == "admin" and credentials.password == "password":
        return TokenResult(access_token=access_security.create_access_token(subject={}))
    else:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

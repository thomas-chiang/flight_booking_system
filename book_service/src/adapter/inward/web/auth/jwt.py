from fastapi_jwt import JwtAccessBearer, JwtAuthorizationCredentials
from datetime import timedelta
from fastapi import Security

access_security = JwtAccessBearer(
    secret_key="secret_key", auto_error=True, access_expires_delta=timedelta(minutes=1)
)


def get_credentials(
    credentials: JwtAuthorizationCredentials = Security(access_security),
) -> JwtAuthorizationCredentials:
    return credentials

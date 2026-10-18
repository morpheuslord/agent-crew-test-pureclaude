"""/api/v1/auth: registration, login, logout, profile, passwords."""

from fastapi import APIRouter, status

from taskboard_api.api.deps import ClientIpDep, PrincipalDep
from taskboard_api.composition import AuthServiceDep
from taskboard_api.domain.commands import (
    ChangePasswordCommand,
    ForgotPasswordCommand,
    LoginCommand,
    RegisterCommand,
    ResetPasswordCommand,
)
from taskboard_api.domain.dtos import LoginResultDTO, UserDTO

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterCommand, auth: AuthServiceDep, client_ip: ClientIpDep) -> UserDTO:
    return auth.register(body, client_ip)


@router.post("/login")
def login(body: LoginCommand, auth: AuthServiceDep, client_ip: ClientIpDep) -> LoginResultDTO:
    return auth.login(body, client_ip)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(principal: PrincipalDep, auth: AuthServiceDep) -> None:
    auth.logout(principal)


@router.get("/me")
def me(principal: PrincipalDep, auth: AuthServiceDep) -> UserDTO:
    return auth.me(principal)


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordCommand, principal: PrincipalDep, auth: AuthServiceDep
) -> None:
    auth.change_password(principal, body)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    body: ForgotPasswordCommand, auth: AuthServiceDep, client_ip: ClientIpDep
) -> dict[str, str]:
    auth.forgot_password(body, client_ip)
    return {"status": "if the account exists, a reset link has been sent"}


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    body: ResetPasswordCommand, auth: AuthServiceDep, client_ip: ClientIpDep
) -> None:
    auth.reset_password(body, client_ip)

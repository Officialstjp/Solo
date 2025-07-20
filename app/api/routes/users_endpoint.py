"""
Module Name: app/api/routes/users_endpoint.py
Purpose   : Endpoint for user management in the Solo API.
Params    : None
History   :
    Date            Notes
    07.19.2025      Init
"""

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.core.db_service import DatabaseService
from app.core.db.users_db import User, UserCreate
from app.core.db.big_brother import PasswordPolicy
from app.api.dependencies import get_db_service
from app.utils.logger import get_logger

logger = get_logger(name="Users_API", json_format=False)

# ---- Authentication models ----
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12, max_length=100)
    remember: bool = Field(default=False)

class RegistrationRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=100)
    full_name: Optional[str] = None

    @validator("username")
    def validate_username(cls, v):
        if not v:
            raise ValueError("Username is required")
        return v

    @validator("email")
    def validate_email(cls, v):
        if not v:
            raise ValueError("Email is required")
        return v

    @validator("password")
    def validate_password(cls, v):
        policy = PasswordPolicy()
        if not policy.validate_password(v): # BigBrother handles all security checks
            raise ValueError("Password does not meet the required policy")
        return v

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user_id: str
    username: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirmReqeust(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def validate_new_password(cls, v):
        policy = PasswordPolicy()
        if not policy.validate_password(v): # BigBrother handles all security checks
            raise ValueError("New password does not meet the required policy")
        return v

# ---- User management models ----
class UserProfile(BaseModel):
    user_id: str
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False # we dont want to expose this in the API, but it's useful for internal logic

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    preferences: Optional[Dict[str, Any]] = None

# User preferences model
class UserPreferences(BaseModel):
    theme: Optional[str] = "dark" # dark default, obviously
    language: Optional[str] = "en"
    notifications_enabled: Optional[bool] = True
    custom_settings: Optional[Dict[str, Any]] = None

def create_router(app: FastAPI) -> APIRouter:
    """
    Create and configrue the users router

    Args:
        app: The FastAPI application instance

    Returns: APIRouter: Configured router with user endpoints
    """
    router = APIRouter(prefix="/auth", tags=["Authentication"])

    async def get_client_info(request: Request):
        """ Helper to get client IP and user agent """
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        return client_ip, user_agent

    @router.post("/register", response_model=User)
    async def register_user(
        request: Request,
        registration: RegistrationRequest,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Register a new user """
        try:
            client_ip, user_agent = await get_client_info(request)
            logger.info(f"User registration attempt from {client_ip} with user agent {user_agent}")

            # check if the user already exists
            # this is handled in BigBrother's credential creation, but we can check here too
            existingUser = await db_service.users.get_user_by_username(registration.username)

            if existingUser:
                logger.warning(f"User {registration.username} already exists.")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already exists"
                )

            # create the user in the database
            user_create = UserCreate(
                username=registration.username,
                email=registration.email,
                password=registration.password,
                full_name=registration.full_name,
                preferences=UserPreferences().dict()
            )

            user = await db_service.users.create_user(
                user=user_create,
                password=registration.password
            )

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User creation failed"
                )

            # log the registration success
            from app.core.db.big_brother import SecurityEvent
            await db_service.bigBrother.log_security_event(SecurityEvent(
                event_type="user_registration",
                user_id=user.user_id,
                username=user.username,
                ip_address=client_ip,
                user_agent=user_agent,
                timestamp=datetime.now()
            ))

            return user

        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
        except Exception as e:
            logger.error(f"Error during user registration: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during registration."
            )

    @router.post("/login", response_model=TokenResponse)
    async def login_user(
        request: Request,
        login: LoginRequest,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Login a user and return an access token """
        try:
            client_ip, user_agent = await get_client_info(request)

            # authenticate the user
            auth_result = await db_service.bigBrother.authenticate(
                username=login.username,
                password=login.password,
                ip_address=client_ip,
                user_agent=user_agent
            )

            if not auth_result:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password"
                )

            # return the token response
            return TokenResponse(
                access_token=auth_result.access_token,
                token_type="bearer",
                expires_in=auth_result.expires_in,
                user_id=auth_result.user_id,
                username=auth_result.username
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during login."
            )

    @router.post("/forgot-password", response_model=dict[str, str])
    async def forgot_password(
        request: Request,
        reset_request: PasswordResetRequest,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Request a password reset link"""
        try:
            client_ip, user_agent = await get_client_info(request)

            # request password reset
            success = await db_service.bigBrother.request_password_reset(
                email=reset_request.email,
                ip_address=client_ip,
                user_agent=user_agent
            )

            # Always return success to prevent email enumeration
            return {
                "message": "If an account with this email exists, a password reset link has been sent."
            }
        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            return {
                "message": "If an account with this email exists, a password reset link has been sent."
            }

    @router.post("/reset-password", response_model=dict[str, str])
    async def reset_password(
        request: Request,
        reset_confirm: PasswordResetConfirmReqeust,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Reset a user's password using a token"""
        try:
            client_ip, user_agent = await get_client_info(request)

            # verify reset tolken and reset password
            user_id = await db_service.bigBrother.verify_password_reset_token(reset_confirm.token)
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired password reset token"
                )

            # reset the password
            success = await db_service.bigBrother.reset_password(
                user_id=user_id,
                new_password=reset_confirm.new_password,
                ip_address=client_ip,
                user_agent=user_agent
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to reset password"
                )

            return {"message": "Password reset successfully. You can now log in with your new password."}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while resetting the password."
            )

    # User Profile Endpoints (protected by auth middleware)
    user_router = APIRouter(prefix="/users", tags=["Users"])

    @user_router.get("/me", response_model=User)
    async def get_current_user(
        request: Request,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Get the current user's profile """
        try:
            user = request.state.user # should be in request state from auth middleware

            # refresh from db
            user_data = await db_service.users.get_user(user.user_id)

            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            return user_data
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting current user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while fetching user profile."
            )

    @user_router.put("/me", response_model=UserProfile)
    async def update_user_profile(
        request: Request,
        profile_update: ProfileUpdateRequest,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Update the current user's profile """
        try:
            user = request.state.user

            # update the user profile
            updated_user = await db_service.users.update_user_profile(
                user_id=user.user_id,
                full_name=profile_update.full_name,
                email=profile_update.email,
                preferences=profile_update.preferences
            )

            if not updated_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update user profile"
                )

            return updated_user
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating user profile."
            )


    @user_router.delete("/me", response_model=dict[str, str])
    async def delete_user_account(
        request: Request,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Delete the current user's account """
        try:
            user = request.state.user

            # delete the user account
            success = await db_service.users.delete_user(user.user_id)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to delete user account"
                )

            return {"message": "User account deleted successfully."}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting user account: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while deleting user account."
            )

    @user_router.get("/preferences", response_model=UserPreferences)
    async def get_user_preferences(
        request: Request,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Get the current user's preferences """
        try:
            user = request.state.user

            # fetch user preferences
            preferences = await db_service.users.get_user_preferences(user.user_id)

            if not preferences:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User preferences not found"
                )

            return preferences
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while fetching user preferences."
            )

    # include the user router in the main router
    app.include_router(user_router)

    return router

"""
Module name : app/core/db/big_brother.py
Purpose     : Security service for authentication, authoriuation, and security monitoring for DB Operations
Params      : None
Change Log:
    Date        Notes
    19.07.2025  Init

Known Issues:
    IP blacklist should be loaded from persistent storag
    We could allow failed rate limit checks to default to True, preventing Lockouts, but i dont't think this is a good idea.

"""

from turtle import st
from typing import Dict, List, Optional, Any, Union, Tuple
import json
import asyncpg
import asyncio
import secrets
import time
import re
import uuid
from datetime import datetime, timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pydantic import BaseModel, Field, EmailStr, validator
import ipaddress
import pyotp

from app.core.db.connection import get_connection_pool
from app.utils.logger import get_logger

# ======= Pydantic models =======

class LoginAttempt(BaseModel):
    """ Model for tracking login attempts """
    user_id: Optional[str] = None
    username: str
    ip_address: str
    user_agent: str
    success: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SecurityEvent(BaseModel):
    """ Model for security related events """
    event_type: str # login_success, login_failure, password_change, etc.
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TOTPSetup(BaseModel):
    """ Model for TOTP setup """
    secret: str
    uri: str
    qr_code: str # base64 encoded QR code

class UserCredentialCreate(BaseModel):
    """ Model for creating user credentials """
    user_id: str
    username: str
    password: str
    email: EmailStr
    totp_enabled: bool = False

    @validator('password')
    def validate_password(cls, value):
        is_valid, reason = PasswordPolicy.validate_password(value)
        if not is_valid:
            raise ValueError(reason)
        return value

class UserCredentialUpdate(BaseModel):
    """ Model for updating user credentials """
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    totp_enabled: Optional[bool] = None
    totp_secret: Optional[str] = None

    @validator('password')
    def validate_password(cls, value):
        if value:
            is_valid, reason = PasswordPolicy.validate_password(value)
            if not is_valid:
                raise ValueError(reason)
        return value

class UserCredential(BaseModel):
    """ Model for user credentials """
    user_id: str
    username: str
    email: EmailStr
    password_hash: str
    totp_enabled: bool = False
    totp_secret: Optional[str] = None
    last_password_change: Optional[datetime] = None
    ackoung_locked: bool = False
    account_locked_until: Optional[datetime] = None
    password_reset_expires: Optional[datetime] = None
    failed_login_attempts: int = 0
    security_level: int = 1 # 1 = standard, 2 = elevated, 3 = admin

# ======= Password Policy ========
class PasswordPolicy:
    """ Password policy configuration """
    MIN_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = "!@#$%^&*()-_=+[]{}|;:'\",.<>?/"
    MAX_REPEATED_CHARS = 3
    CHECK_COMMON_PASSWORDS = True
    COMMON_PASSWORDS_FILE = "common_passwords.txt"
    PASSWORD_HISTORY_COUNT = 10 # remember last 10 passwords
    PASSWORD_MAX_AGE_DAYS = 730 # 2 years

    @classmethod
    def validate_password(cls, password: str) -> tuple[bool, str]:
        """
        Validate a password against the policy

        Returns:
            tuple: (is_valid: bool, message: str)
        """
        # check length
        if len(password) < cls.MIN_LENGTH:
            return False, f"Password must be at least {cls.MIN_LENGTH} characters long."

        # check character requirements
        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            return False, "Pasword must contain at least one uppercase letter"
        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        if cls.REQUIRE_DIGITS and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        if cls.REQUIRE_SPECIAL and not any(c in cls.SPECIAL_CHARS for c in password):
            return False, f"Password must contain at least one special character."

        # check for repeated characters
        if cls.MAX_REPEATED_CHARS:
            for i in range(len(password) - cls.MAX_REPEATED_CHARS + 1):
                if len(set(password[i:i+cls.MAX_REPEATED_CHARS])) == 1:
                    return False, f"Password cannot contain more than {cls.MAX_REPEATED_CHARS} repeated characters"

        # check against common passwords list
        if cls.CHECK_COMMON_PASSWORDS:
            try:
                with open(cls.COMMON_PASSWORDS_FILE, 'r') as f:
                    common_passwords = set(line.strip() for line in f)
                    if password.lower() in common_passwords:
                        return False, "Passord detected on common password list, please choose a different password."
            except FileNotFoundError:
                pass
        return True, "Password meets all requirements"

# ====== Rate Limiting ======
class RateLimiter:
    """ Rate limiting for sensitive operations """

    def __init__(self):
        self.logger = get_logger("big_brother.RateLimiter")

        # Rate limit configuration
        self.login_limits = {
            "window_seconds": 60,  # 1 minute
            "max_attempts": 5,  # max attempts in the window
            "lockout_seconds": 60,  # lockout for 1 minute after max
        }

        self.password_reset_limits = {
            "window_seconds": 3600,  # 1 hour
            "max_attempts": 3,  # max attempts in the window
        }

        self.ip_blacklist = set() # should be loaded from persistent storage
        self.temp_blacklist = {}

    async def check_login_rate_limits(self, username: str, ip_address: str) -> Tuple[bool, str]:
        """
        Check if login attempts exceed rate limits

        Returns:
            tuple: (is_allowed: bool, message: str)
        """
        try:
            if ip_address in self.ip_blacklist:
                return False, "IP address is blacklisted."

            # check temp blacklist
            current_time = time.time()
            if ip_address in self.temp_blacklist:
                if current_time < self.temp_blacklist[ip_address]:
                    expiry_time = datetime.fromtimestamp(self.temp_blacklist[ip_address])
                    return False, f"Too many attempts. Try again after {expiry_time}."
                else:
                    # remove from temporary blacklist if expired
                    del self.temp_blacklist[ip_address]

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # check account lock status
                AccountLockQuery = """
                    SELECT account_locked, account_locked_until
                    FROM security.credentials
                    WHERE username = $1
                """

                account_lock_result = await conn.fetchrow(AccountLockQuery, username)
                if account_lock_result and account_lock_result['account_locked']:
                    if account_lock_result['account_locked_until'] and account_lock_result['account_locked_until'] > datetime.utcnow():
                        return False, f"Account is locked until {account_lock_result['account_locked_until']}."

                # check login attempts in the last window
                window_start = datetime.utcnow() - timedelta(seconds=self.login_limits['window_seconds'])
                LoginAttemptsQuery = """
                    SELECT COUNT(*) FROM security.login_attempts
                    WHERE (username = $1 OR ip_address = $2)
                    AND success = FALSE
                    AND timestamp >= $3
                """

                recent_attempts = await conn.fetchval(LoginAttemptsQuery, username, ip_address, window_start)

                if recent_attempts >= self.login_limits['max_attempts']:
                    # add to temporary blacklist
                    expiry_time = current_time + (self.login_limits['window_seconds'] * 2)  # double the window for temp blacklist
                    self.temp_blacklist[ip_address] = expiry_time

                    # update account lock status
                    lock_until = datetime.utcnow() + timedelta(minutes=self.login_limits['lockout_seconds']) # lock for specified duration
                    UpdateLockQuery = """
                    UPDATE security.credentials
                    SET account_locked = TRUE, account_locked_until = $1
                    WHERE username = $2
                    """
                    await conn.execute(UpdateLockQuery, lock_until, username)

                    return False, f"Too many login attempts. Account locked until {lock_until}."

            return True, "Rate limit check passed."

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during rate limit check: {e}")
            return False, "Internal server error. Please try again later." # maybe default to true?
        except Exception as e:
            self.logger.error(f"Unexpected error during rate limit check: {e}")
            return False, "Internal server error. Please try again later." # maybe default to true?

    async def record_login_attempt(self, attempt: LoginAttempt) -> None:
        """
        Record a login attempt in the database

        Args:
            attempt (LoginAttempt): The login attempt to record
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                InsertQuery = """
                    INSERT INTO security.login_attempts (user_id, username, ip_address, user_agent, success, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """
                await conn.execute(InsertQuery, attempt.user_id, attempt.username, attempt.ip_address,
                                   attempt.user_agent, attempt.success, attempt.timestamp)

                # reset failed attempts counter on success
                if attempt.success and attempt.user_id:
                    ResetAttemptsQuery = """
                        UPDATE security.credentials
                        SET failed_login_attempts = 0, account_locked = FALSE, account_locked_until = NULL
                        WHERE user_id = $1
                    """
                    await conn.execute(ResetAttemptsQuery, attempt.user_id)

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during login attempt recording: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during login attempt recording: {e}")

    async def check_password_reset_rate_limits(self, email: str, ip_address: str) -> Tuple[bool, str]:
        """
        Check if password reset attempts exceed rate limits

        Args:
            email (str): Email address
            ip_address (str): Client IP address

        Returns:
            tuple: (is_allowed: bool, message: str)
        """
        try:
            if ip_address in self.ip_blacklist:
                return False, "IP address is blacklisted."

            # Check temp blacklist
            current_time = time.time()
            if ip_address in self.temp_blacklist:
                if current_time < self.temp_blacklist[ip_address]:
                    expiry_time = datetime.fromtimestamp(self.temp_blacklist[ip_address])
                    return False, f"Too many reset attempts. Try again after {expiry_time}."
                else:
                    # Remove from temporary blacklist if expired
                    del self.temp_blacklist[ip_address]

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Check password reset attempts in the rate limit window
                window_start = datetime.utcnow() - timedelta(seconds=self.password_reset_limits['window_seconds'])

                # Query to count reset attempts by email or IP
                ResetAttemptsQuery = """
                    SELECT COUNT(*) FROM security.security_events
                    WHERE (details->>'email' = $1 OR ip_address = $2)
                    AND event_type = 'password_reset_token_requested'
                    AND timestamp >= $3
                """

                recent_attempts = await conn.fetchval(ResetAttemptsQuery, email, ip_address, window_start)

                if recent_attempts >= self.password_reset_limits['max_attempts']:
                    # Add to temporary blacklist
                    expiry_time = current_time + self.password_reset_limits['window_seconds']
                    self.temp_blacklist[ip_address] = expiry_time

                    return False, f"Too many password reset attempts. Please try again later."

            return True, "Rate limit check passed."

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during password reset rate limit check: {e}")
            return False, "Internal server error. Please try again later."
        except Exception as e:
            self.logger.error(f"Unexpected error during password reset rate limit check: {e}")
            return False, "Internal server error. Please try again later."
# ====== Security Service Class ======

class BigBrother:
    """
    Comprehensive security service for authentication, authorization, and security monitoring
    """

    def __init__(self):
        self.logger = get_logger("big_brother")
        self.password_hasher = PasswordHasher(
            time_cost=3,        # Number of iterations
            memory_cost=65536,  # Memory usage in kibibytes (64MB)
            parallelism=2,      # Number of threads to use
            hash_len=32,        # Length of the hash in bytes
            salt_len=16         # Length of the salt in bytes
        )
        self.rate_limiter = RateLimiter()

    async def initialize(self):
        """ Initialize the security service """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # check if schema exists
                schema_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'security')"
                )

                if not schema_exists:
                    self.logger.error("Security schema does not exist. Please ensure the database is running and initialized.")
                    return False

                credentials_table_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'security' AND table_name = 'credentials')"
                )
                if not credentials_table_exists:
                    self.logger.error("Credentials table does not exist. Please ensure the database is initialized.")
                    return False

                login_attempts_table_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'security' AND table_name = 'login_attempts')"
                )
                if not login_attempts_table_exists:
                    self.logger.error("Login attempts table does not exist. Please ensure the database is initialized.")
                    return False

                password_history_table_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'security' AND table_name = 'password_history')"
                )
                if not password_history_table_exists:
                    self.logger.error("Password history table does not exist. Please ensure the database is initialized.")
                    return False

                security_events_table_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'security' AND table_name = 'security_events')"
                )
                if not security_events_table_exists:
                    self.logger.error("Security events table does not exist. Please ensure the database is initialized.")
                    return False

                # Load IP blacklist from persistent storage if needed
                # For now, just an empty set
                self.rate_limiter.ip_blacklist = set()

            return True
        except Exception as e:
            self.logger.error(f"Error initializing security service: {e}")
            return False

    # ======= Authentication =======

    async def validate_token(self, token: str, ip_address: str, user_agent: str) -> Optional[Dict[str, Any]]:
        """
        Validate a JWT token and return user information if valid

        Args:
            token: The JWT token to validate
            ip_address: The IP address of the client
            user_agent: The user agent of the client

        Returns:
            Optional[Dict[str, Any]]: User information if token is valid, None otherwise
        """
        try:
            # For now, just return a mock user for testing
            # In a real implementation, this would verify the JWT token
            # and retrieve the user from the database
            self.logger.info(f"Token validation requested from {ip_address}")

            # Mock implementation for development - always succeeds
            # TODO: Implement proper JWT validation
            mock_user = {
                "user_id": "12345",
                "username": "test_user",
                "email": "test@example.com",
                "roles": ["user"],
                "permissions": ["read:all", "write:own"],
                "is_active": True
            }

            # Log the validation event
            await self.log_security_event(SecurityEvent(
                event_type="token_validation_success",
                user_id=mock_user["user_id"],
                username=mock_user["username"],
                ip_address=ip_address,
                user_agent=user_agent,
                details={"token_prefix": token[:10] + "..." if token else None}
            ))

            return mock_user

        except Exception as e:
            self.logger.error(f"Error validating token: {str(e)}")

            # Log the failed validation
            await self.log_security_event(SecurityEvent(
                event_type="token_validation_failure",
                ip_address=ip_address,
                user_agent=user_agent,
                details={"error": str(e), "token_prefix": token[:10] + "..." if token else None}
            ))

            return None

    async def create_user_credentials(self, credentials: UserCredentialCreate) -> Optional[str]:
        """
        Create user credentials

        Args:
            credentials: UserCredentialCreate model

        Returns:
            Optional[str]: User ID if successful, None otherwise
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # hash the password
                password_hash = self.password_hasher.hash(credentials.password)

                # check if username or email already exists
                ExistingUserQuery = """
                    SELECT user_id FROM security.credentials
                    WHERE username = $1 OR email = $2
                """
                existing_user = await conn.fetchval(ExistingUserQuery, credentials.username, credentials.email)
                if existing_user:
                    self.logger.warning("User with this username or email already exists.")
                    return None

                # insert new user credentials
                InsertQuery = """
                    INSERT INTO security.credentials (user_id, username, password_hash, email, totp_enabled)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING user_id
                """
                await conn.execute(InsertQuery, credentials.user_id, credentials.username, password_hash, credentials.email, credentials.totp_enabled)

                # record the inial password in history
                InsertHistoryQuery = """
                    INSERT INTO security.password_history (user_id, password_hash, changed_at)
                    VALUES ($1, $2, NOW())
                """
                await conn.execute(InsertHistoryQuery, credentials.user_id, password_hash)

                # log the security event
                await self.log_security_event(SecurityEvent(
                    event_type="user_created",
                    user_id=credentials.user_id,
                    username=credentials.username,
                    details={"email": credentials.email}
                ))

                return credentials.user_id

        except Exception as e:
            self.logger.error(f"Failed to create user credentials: {e}")
            return None

    async def authenticate(self, username: str, password: str, ip_address: str, user_agent: str,
                           totp_code: Optional[str] = None) -> Tuple[bool, Optional[str], str]:
        """
        Authenticate a user

        Args:
            username (str): Username
            password (str): Password
            ip_address (str): Client IP address
            user_agent (str): Client user agent
            totp_code: Time-based one-time password (if MFA enabled)

        Returns:
            Tuple[bool, Optional[str], str]: (success, user_id, message)
        """
        try:
            # Check rate limits first
            rate_limit_check, message = await self.rate_limiter.check_login_rate_limits(username, ip_address)
            if not rate_limit_check:
                await self.log_security_event(SecurityEvent(
                    event_type="login_rate_limited",
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"reason": message}
                ))
                return False, None, message

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # get user credentials
                UserCredsQuery = """
                    SELECT user_id, password_hash, totp_enabled, totp_secret
                    FROM security.credentials
                    WHERE username = $1
                """
                user_creds = await conn.fetchrow(UserCredsQuery, username)

                if not user_creds:
                    # record failed login attempt
                    await self.rate_limiter.record_login_attempt(LoginAttempt(
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False
                    ))

                    await self.log_security_event(SecurityEvent(
                        event_type="login_failure",
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        details={"reason": "User not found"}
                    ))

                    # minimally random timing to prevent username enumeration
                    await asyncio.sleep(secrets.randbelow(2))  # sleep for 0-1 seconds
                    return False, None, "Invalid username or password."

                # check if account is locked
                if user_creds['account_locked']:
                    if user_creds['account_locked_until'] and user_creds['account_locked_until'] > datetime.utcnow():
                        await self.log_security_event(SecurityEvent(
                            event_type="login_blocked",
                            user_id=user_creds['user_id'],
                            username=username,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            details={"reason": "Account is locked until " + str(user_creds['account_locked_until'])}
                        ))
                        return False, None, f"Account is locked until {user_creds['account_locked_until']}."

                    # unlock the account if lockout period has expired
                    UnlockQuery = """
                        UPDATE security.credentials
                        SET account_locked = FALSE, account_locked_until = NULL
                        WHERE user_id = $1
                    """
                    await conn.execute(UnlockQuery, user_creds['user_id'])

                # verify password
                try:
                    self.password_hasher.verify(user_creds['password_hash'], password)

                    # check for password hash update need
                    if self.password_hasher.check_needs_rehash(user_creds['password_hash']):
                        new_hash = self.password_hasher.hash(password)
                        UpdatePasswordQuery = """
                            UPDATE security.credentials
                            SET password_hash = $1, last_password_change = NOW()
                            WHERE user_id = $2
                        """
                        await conn.execute(UpdatePasswordQuery, new_hash, user_creds['user_id'])

                        # record the new password in history
                        InsertHistoryQuery = """
                            INSERT INTO security.password_history (user_id, password_hash, changed_at)
                            VALUES ($1, $2, NOW())
                        """
                        await conn.execute(InsertHistoryQuery, user_creds['user_id'], new_hash)

                    # check TOTP if enabled
                    if user_creds['totp_enabled']:
                        if not totp_code:
                            return False, None, "TOTP code required."

                        totp = pyotp.TOTP(user_creds['totp_secret'])
                        if not totp.verify(totp_code):
                            await self.rate_limiter.record_login_attempt(LoginAttempt(
                                user_id=user_creds['user_id'],
                                username=username,
                                ip_address=ip_address,
                                user_agent=user_agent,
                                success=False
                            ))
                            await self.log_security_event(SecurityEvent(
                                event_type="login_failure",
                                user_id=user_creds['user_id'],
                                username=username,
                                ip_address=ip_address,
                                user_agent=user_agent,
                                details={"reason": "Invalid TOTP code"}
                            ))

                            return False, None, "Invalid TOTP code."

                    # record successful login attempt
                    await self.rate_limiter.record_login_attempt(LoginAttempt(
                        user_id=user_creds['user_id'],
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=True
                    ))

                    await self.log_security_event(SecurityEvent(
                        event_type="login_success",
                        user_id=user_creds['user_id'],
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        details={"security_level": user_creds['security_level']}
                    ))

                    return True, user_creds['user_id'], "Authentication successful."

                except VerifyMismatchError:
                    # record failed login attempt
                    await self.rate_limiter.record_login_attempt(LoginAttempt(
                        user_id=user_creds['user_id'],
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False
                    ))

                    await self.log_security_event(SecurityEvent(
                        event_type="login_failure",
                        user_id=user_creds['user_id'],
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        details={"reason": "Invalid password"}
                    ))

                    return False, None, "Invalid username or password."

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during authentication: {e}")
            return False, None, "Internal server error. Please try again later."
        except Exception as e:
            self.logger.error(f"Unexpected error during authentication: {e}")
            return False, None, "Internal server error. Please try again later."

    async def change_password(self, user_id: str, current_password: str,
                              new_password: str, ip_address: str, user_agent: str) -> Tuple[bool, str]:
        """
        Change user password

        Args:
            user_id (str): User ID
            current_password (str): Current password
            new_password (str): New password
            ip_address (str): Client IP address
            user_agent (str): Client user agent

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # validate new password
            is_valid, reason = PasswordPolicy.validate_password(new_password)
            if not is_valid:
                return False, reason

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # get user credentials
                UserCredsQuery = """
                    SELECT user_id, password_hash, totp_enabled, totp_secret
                    FROM security.credentials
                    WHERE user_id = $1
                """
                user_creds = await conn.fetchrow(UserCredsQuery, user_id)

                if not user_creds:
                    return False, "User not found."

                # verify current password
                try:
                    self.password_hasher.verify(user_creds['password_hash'], current_password)
                except VerifyMismatchError:
                    return False, "Current password is incorrect."

                # check if new password is same as current or in history
                if self.password_hasher.verify(user_creds['password_hash'], new_password):
                    return False, "New password cannot be the same as the current password."

                # check password history
                PasswordHistoryQuery = """
                    SELECT password_hash
                    FROM security.password_history
                    WHERE user_id = $1
                    ORDER BY changed_at DESC
                    LIMIT $2
                """

                password_history = await conn.fetch(PasswordHistoryQuery, user_id, PasswordPolicy.PASSWORD_HISTORY_COUNT)

                for history_record in password_history:
                    try:
                        self.password_hasher.verify(history_record['password_hash'], new_password)
                        # if verification succeeds, password is in history
                        return False, f"Password has been used in the last {PasswordPolicy.PASSWORD_HISTORY_COUNT} changes. Please choose a different password."
                    except VerifyMismatchError:
                        # this is good, password is not in history
                        pass

                # hash the new password
                new_hash = self.password_hasher.hash(new_password)

                # update the password
                UpdatePasswordQuery = """
                    UPDATE security.credentials
                    SET password_hash = $1, last_password_change = NOW()
                    WHERE user_id = $2
                """
                await conn.execute(UpdatePasswordQuery, new_hash, user_id)

                # record the new password in history
                InsertHistoryQuery = """
                    INSERT INTO security.password_history (user_id, password_hash, changed_at)
                    VALUES ($1, $2, NOW())
                """
                await conn.execute(InsertHistoryQuery, user_id, new_hash)

                await self.log_security_event(SecurityEvent(
                    event_type="password_change",
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"security_level": user_creds['security_level']}
                ))

                return True, "Password changed successfully."

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during password change: {e}")
            return False, "Internal server error. Please try again later."
        except Exception as e:
            self.logger.error(f"Unexpected error during password change: {e}")
            return False, "Internal server error. Please try again later."

# ========= Multi-Factor Authentication =========

    async def setup_totp(self, user_id: str, username: str) -> TOTPSetup:
        """
        Set up TOTP (Time-based One-Time Password) for a user

        Args:
            user_id (str): User ID

        Returns:
            Optional[TOTPSetup]: TOTP setup details including secret, URI, and QR code
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # get user info
                UserInfoQuery = """
                    SELECT totp_enabled, totp_secret FROM security.credentials WHERE user_id = $1
                """
                user_info = await conn.fetchrow(UserInfoQuery, user_id)

                if not user_info:
                    return None

                # Generate TOTP secret
                totp_secret = pyotp.random_base32()
                totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="SoloApp")

                # Generate QR code (base64 encoded)
                qr_code_base64 = None
                try:
                    import qrcode
                    import base64
                    from io import BytesIO

                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(totp_uri)
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    qr_code_b64 = base64.b64encode(buffer.getvalue()).decode()
                except ImportError:
                    # QR code generation is optional
                    self.logger.warning("QR code generation failed: qrcode package not installed")
                    qr_code_b64 = None
                except Exception as e:
                    self.logger.warning(f"QR code generation failed: {str(e)}")
                    qr_code_b64 = None

                return TOTPSetup(
                    secret=totp_secret,
                    uri=totp_uri,
                    qr_code=qr_code_b64
                )
        except Exception as e:
            self.logger.error(f"Error setting up TOTP for user {user_id}: {e}")
            return None

    async def enable_totp(self, user_id: str, totp_secret: str, verification_code: str) -> bool:
        """
        Enable TOTP for a user after verification

        Args:
            user_id (str): User ID
            totp_secret (str): TOTP secret to enable
            verification_code (str): Verification code from TOTP app

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # verify the TOTP code
            totp = pyotp.TOTP(totp_secret)
            if not totp.verify(verification_code):
                self.logger.warning(f"TOTP verification failed for user {user_id}.")
                return False

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # update user credentials to enable TOTP
                UpdateQuery = """
                    UPDATE security.credentials
                    SET totp_enabled = TRUE, totp_secret = $1
                    WHERE user_id = $2
                """
                result = await conn.execute(UpdateQuery, totp_secret, user_id)

                if result == "UPDATE 1":
                    # get username for logging
                    username = await conn.fetchval("""
                        SELECT username FROM security.credentials WHERE user_id = $1
                    """, user_id)

                    await self.log_security_event(SecurityEvent(
                        event_type="totp_enabled",
                        user_id=user_id,
                        username=username,
                        details={"totp_secret": totp_secret}
                    ))

                    return True
                return False
        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during TOTP enable: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during TOTP enable: {e}")
            return False

    async def disable_totp(self, user_id: str, password: str) -> bool:
        """
        Disable TOTP for a user

        Args:
            user_id (str): User ID
            password (str): Current password for verification

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # get user credentials
                UserCredsQuery = """
                    SELECT user_id, password_hash FROM security.credentials WHERE user_id = $1
                """
                user_creds = await conn.fetchrow(UserCredsQuery, user_id)

                if not user_creds:
                    return False

                # verify current password
                try:
                    self.password_hasher.verify(user_creds['password_hash'], password)
                except VerifyMismatchError:
                    return False

                # update user credentials to disable TOTP
                UpdateQuery = """
                    UPDATE security.credentials
                    SET totp_enabled = FALSE, totp_secret = NULL
                    WHERE user_id = $1
                """
                result = await conn.execute(UpdateQuery, user_id)

                if result == "UPDATE 1":
                    # log the security event
                    await self.log_security_event(SecurityEvent(
                        event_type="totp_disabled",
                        user_id=user_id,
                        details={"totp_secret": None}
                    ))
                    return True
                return False

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during TOTP disable: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during TOTP disable: {e}")
            return False

    # ========= Password Reset =========

    async def create_password_reset_token(self, email: str, ip_address: str) -> Tuple[bool, str]:
        """
        Create a password reset token

        Args:
            email (str): User email
            ip_address (str): Client IP address

        Returns:
            Tuple[bool, str]: (success, message or token)
        """
        try:
            # Check rate limits first
            rate_limit_check, message = await self.rate_limiter.check_password_reset_rate_limits(email, ip_address)
            if not rate_limit_check:
                await self.log_security_event(SecurityEvent(
                    event_type="password_reset_rate_limited",
                    ip_address=ip_address,
                    details={"reason": message, "email": email}
                ))
                return False, message

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # find user by email
                UserQuery = """
                    SELECT user_id, username FROM security.credentials WHERE email = $1
                """
                user = await conn.fetchrow(UserQuery, email)

                if not user:
                    return True, "If an account with this email exists, a password reset link has been sent."

                # Generate a token
                reset_token = secrets.token_urlsafe(32)

                # set expiration time (1 hour from now)
                expiration_time = datetime.utcnow() + timedelta(hours=1)

                # store token in the database
                InsertTokenQuery = """
                    UPDATE security.credentials
                    SET password_reset_token = $1, password_reset_expiration = $2
                    WHERE user_id = $3
                """
                await conn.execute(InsertTokenQuery, reset_token, expiration_time, user['user_id'])

                await self.log_security_event(SecurityEvent(
                    event_type="password_reset_token_requested",
                    user_id=user['user_id'],
                    username=user['username'],
                    details={"email": email, "token": reset_token if user else None}
                ))

                # send email with reset link ('return' is a placeholder, implement actual email sending)
                # reset_link = f"https://yourapp.com/reset-password?token={reset_token}"
                # await send_email(email, "Password Reset", f"Click here to reset your password: {reset_link}")
                return True, reset_token

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during password reset token creation: {e}")
            return False, "Internal server error. Please try again later."
        except Exception as e:
            self.logger.error(f"Unexpected error during password reset token creation: {e}")
            return False, "Internal server error. Please try again later."

    async def verify_reset_token(self, token: str) -> Optional[str]:
        """
        Verify a password reset token

        Args:
            token (str): Password reset token

        Returns:
            Optional[str]: User ID if token is valid, None otherwise
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # check if token exists and is not expired
                TokenQuery = """
                    SELECT user_id, username
                    FROM security.credentials
                    WHERE password_reset_token = $1 AND password_reset_expiration > NOW()
                """
                user = await conn.fetchrow(TokenQuery, token)

                if not user:
                    return None

                await self.log_security_event(SecurityEvent(
                    event_type="password_reset_token_verified",
                    user_id=user['user_id'],
                    username=user['username'],
                ))

                return user['user_id']

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during password reset token verification: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during password reset token verification: {e}")
            return None

    async def reset_password_with_token(self, token: str, new_password: str) -> Tuple[bool, str]:
        """
        Reset password using a valid token

        Args:
            token (str): Password reset token
            new_password (str): New password

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # validate new password
            is_valid, reason = PasswordPolicy.validate_password(new_password)
            if not is_valid:
                return False, reason

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # find token and check expiration
                    TokenQuery = """
                        SELECT user_id, username, password_reset_token
                        FROM security.credentials
                        WHERE password_reset_token = $1 AND password_reset_expiration > NOW()
                    """
                    user = await conn.fetchrow(TokenQuery, token)

                    if not user:
                        return False, "Invalid or expired token."

                    # check password history
                    PasswordHistoryQuery = """
                        SELECT password_hash
                        FROM security.password_history
                        WHERE user_id = $1
                        ORDER BY changed_at DESC
                        LIMIT $2
                    """
                    password_history = await conn.fetch(PasswordHistoryQuery, user['user_id'], PasswordPolicy.PASSWORD_HISTORY_COUNT)

                    for history_record in password_history:
                        try:
                            self.password_hasher.verify(history_record['password_hash'], new_password)
                            # if verification succeeds, password is in history
                            return False, f"Password has been used in the last {PasswordPolicy.PASSWORD_HISTORY_COUNT} changes. Please choose a different password."
                        except VerifyMismatchError:
                            # password is not in history
                            pass

                    # hash the new password
                    new_hash = self.password_hasher.hash(new_password)

                    # update the password and clear the reset token
                    UpdateQuery = """
                        UPDATE security.credentials
                        SET password_hash = $1, last_password_change = NOW(),
                            password_reset_token = NULL, password_reset_expiration = NULL
                        WHERE user_id = $2
                    """
                    await conn.execute(UpdateQuery, new_hash, user['user_id'])

                    # record the new password in history
                    InsertHistoryQuery = """
                        INSERT INTO security.password_history (user_id, password_hash, changed_at)
                        VALUES ($1, $2, NOW())
                    """
                    await conn.execute(InsertHistoryQuery, user['user_id'], new_hash)

                    await self.log_security_event(SecurityEvent(
                        event_type="password_reset",
                        user_id=user['user_id'],
                        username=user['username'],
                    ))

                    return True, "Password reset successfully."
        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during password reset: {e}")
            return False, "Internal server error. Please try again later."
        except Exception as e:
            self.logger.error(f"Unexpected error during password reset: {e}")
            return False, "Internal server error. Please try again later."

    # ========= Security Monitoring and Logging =========

    async def log_security_event(self, event: SecurityEvent) -> bool:
        """ Log a security event to the database """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                InsertEventQuery = """
                    INSERT INTO security.security_events (event_type, user_id, username, ip_address, user_agent, details, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """
                await conn.execute(InsertEventQuery, event.event_type, event.user_id, event.username,
                                   event.ip_address, event.user_agent, json.dumps(event.details or {}), event.timestamp)

                # Log to application log for critical events
                critical_events = [
                    "login_blocked",
                    "account_locked",
                    "brute_force_detected",
                    "suspicious_activity",
                    "admin_access",
                    "security_settings_changed"
                ]
                if event.event_type in critical_events:
                    self.logger.warning(f"Security Event: {event.event_type} for user {event.username} ({event.user_id}) - {event.details}")

                return True

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during security event logging: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during security event logging: {e}")
            return False

    async def get_user_security_events(self, user_id: str, limit: int = 100) -> List[SecurityEvent]:
        """
        Get security events for a user

        Args:
            user_id (str): User ID
            limit (int): Number of events to retrieve

        Returns:
            List[SecurityEvent]: List of security events
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                SelectEventsQuery = """
                    SELECT event_type, user_id, username, ip_address, user_agent, details, created_at
                    FROM security.security_events
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """
                rows = await conn.fetch(SelectEventsQuery, user_id, limit)

                return [SecurityEvent(
                    event_type=row['event_type'],
                    user_id=row['user_id'],
                    username=row['username'],
                    ip_address=row['ip_address'],
                    user_agent=row['user_agent'],
                    details=json.loads(row['details']) if row['details'] else None,
                    created_at=row['created_at']
                ) for row in rows]

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during fetching security events: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error during fetching security events: {e}")
            return []

    # ======== Authorization and Access Control ========

    async def check_permission(self, user_id: str, permission: str) -> bool:
        """
        Check if a user has a specific permission

        Args:
            user_id (str): User ID
            permission (str): Permission to check

        Returns:
            bool: True if user has permission, False otherwise
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # get user security level
                SecurityLevelQuery = """
                    SELECT security_level FROM security.credentials WHERE user_id = $1
                """
                security_level = await conn.fetchval(SecurityLevelQuery, user_id)

                if not security_level:
                    return False

                # simple role based permissions for now, we should expand this later
                admin_permissions = ["admin", "user_management", "security_settings", "system_config"]
                elevated_permissions = ["elevated", "content_management", "reports"]
                standard_permissions = ["standard", "view_content", "edit_profile"]

                if security_level >= 3 and permission in admin_permissions:
                    return True
                elif security_level >= 2 and permission in elevated_permissions:
                    return True
                elif security_level >= 1 and permission in standard_permissions:
                    return True

                return False

        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during permission check: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during permission check: {e}")
            return False

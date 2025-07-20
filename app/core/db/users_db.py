"""
Module Name: app/core/db/users_db.py
Purpose    : Databsase service for user management operations
Params     : None
Change Log:
    Date            Notes
    18.07.2025      Init
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import json
import asyncpg
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, EmailStr, validator

from app.core.db.connection import get_connection_pool
from app.utils.logger import get_logger

# ======= Pydantic models ========

# --------- User models ---------
class UserBase(BaseModel):
    """ Base model for user data """
    username: str
    email: EmailStr
    full_name: Optional[str]

class UserCreate(UserBase):
    """ Model for creating a new user """
    preferences: Optional[Dict[str, Any]] = None

class User(UserBase):
    """ Complete user model with all fields """
    user_id: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    preferences: Optional[Dict[str, Any]] = None

# --------- Session models ---------
class SessionBase(BaseModel):
    """ Base model for session data """
    user_id: str

class SessionCreate(SessionBase):
    """ Model for creating a new session """
    metadata: Optional[Dict[str, Any]] = None

class Session(SessionBase):
    """ Complete session model with all fields """
    session_id: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    status: str = "active"
    metadata: Optional[Dict[str, Any]] = None

# --------- Conversation models ---------
class ConversationBase(BaseModel):
    """ Base model for converstation data """
    session_id: str
    title: Optional[str] = None

class ConversationCreate(ConversationBase):
    """ Model for creating a new conversation """
    metadata: Optional[Dict[str, Any]] = None

class Conversation(ConversationBase):
    """ Complete conversation model with all fields """
    conversation_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# -------- Message models ---------
class MessageBase(BaseModel):
    """ Base model for message data """
    conversation_id: str
    role: str # user, assistant, system
    content: str

class MessageCreate(MessageBase):
     """ Model for creating a new message """
     model_id: Optional[str] = None
     request_id: Optional[str] = None
     tokens: Optional[int] = None
     metadata: Optional[Dict[str, Any]] = None

class Message(MessageBase):
    """ Complete message with all fields """
    message_id: str
    created_ad: Optional[datetime] = None
    model_id: Optional[str] = None
    request_id: Optional[str] = None
    tokens: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

# ======= Database service class ========
class UsersDatabase:
    """
    Database service for user management operations
    """
    def __init__(self):
        """ Initalize the logger at __init__ """
        self.logger = get_logger("users_db")
        self.logger.info("User DB service initialized.")

    async def initialize(self):
        """ Initalize the User DB service, get connection pool and check if schema exists"""
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                SQLBase = "SELECT EXISTS(SELECT 1 from pg_namespace WHERE nspname = 'users'"
                SQLclose = ")"

                schema_exists = await conn.fetchval(
                    SQLBase + SQLclose
                )
                if not schema_exists:
                    self.logger.warning("Users schema doesn't exist, Some model operations may fail.")

                usersSQL = SQLBase + " AND tablename = 'users'" + SQLclose
                users_exists = await conn.fetchval(
                    usersSQL
                )
                if not users_exists:
                    self.logger.warning("Users table doesn't exist, Some model operations may fail.")

                sessionsSQL = SQLBase + " AND tablename = 'sessions'" + SQLclose
                sessions_exists = await conn.fetchval(
                    sessionsSQL
                )
                if not sessions_exists:
                    self.logger.warning("Sessions table doesn't exist, Some model operations may fail.")

                conversationsSQL = SQLBase + " AND tablename = 'conversations'" + SQLclose
                conversations_exists = await conn.fetchval(
                    conversationsSQL
                )
                if not conversations_exists:
                    self.logger.warning("Conversations table doesn't exist, Some model operations may fail.")

                messagesSQL = SQLBase + " AND tablename = 'messages'" + SQLclose
                messages_exists = await conn.fetchval(
                    messagesSQL
                )
                if not messages_exists:
                    self.logger.warning("Messages table doesn't exist, Some model operations may fail.")
            self.logger.info("Users database service initialized successfully.")
            return True
        except asyncpg.PostgresError as e:
            self.logger.error(f"Database error during initialization: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during initialization: {e}")

    # ========== User operations ==========
    async def create_user(self, user: UserCreate, password: str = None) -> Optional[User]:
        """
        Create a new User

        Args:
            user: UserCreate model with user data
            password: Optional password (if using credentials system)

        Returns:
            User model if successful, None if otherwise
        """
        try:
            # generate a user id
            user_id = f"user_{secrets.token_hex(8)}"

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # convert Pydantic to dict
                user_dict = user.model_dump()

                # Extract specific fields
                username = user_dict.get('username')
                email = user_dict.get('email')
                full_name = user_dict.get('full_name')
                preferences = user_dict.get('preferences')

                userCreateSQL = """
                    INSERT INTO users.users
                    (user_id, name, preferences)
                    VALUES ($1, $2, $3)
                    RETURNING user_id, name, created_at, last_active, preferences
                """
                # execute query
                result = await conn.fetchrow(userCreateSQL, user_id, full_name, json.dumps(preferences) if preferences else None)

                if result:
                    # if password is provided, create credentials
                    if password is not None:
                        from app.core.db.big_brother import BigBrother, UserCredentialCreate

                        credential_create = UserCredentialCreate(
                            user_id=user_id,
                            username=username,
                            email=email,
                            password=password
                        )

                        cred_result = await BigBrother.create_user_credentials(credential_create)
                        if not cred_result:
                            raise ValueError("Failed to create user credentials")

                    # convert to pydantic
                    return User(
                        user_id=result['user_id'],
                        username=username,
                        email=email,
                        full_name=result['name'],
                        created_at=result['created_at'],
                        last_active=result['last_active'],
                        preferences=result['preferences']
                    )
                return None
        except Exception as e:
            self.logger.error(f"Failed to create user: {str(e)}")
            return None

    async def get_user(self, user_id: str) -> Optional[User]:
        """
        Get a user by id

        Args:
            user_id: the user id string to fetch from the DB

        Returns:
            User model if successful, None if otherwise
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                userSQL = """
                    SELECT user_id, username, email, full_name, created_at, last_active, preferences
                    FROM users.users
                    WHERE user_id = $1
                """
                result = await conn.fetchrow(userSQL, user_id)
                if result:
                    return User(
                        user_id = result['user_id'],
                        username = result['username'],
                        email = result['email'],
                        full_name = result['full_name'],
                        created_at = result['created_at'],
                        last_active = result['last_active'],
                        preferences = result['preferences']
                    )
                return None
        except Exception as e:
            self.logger.error(f"Failed to get user: {str(e)}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username

        Args:
            username: the username string to fetch from the DB

        Returns:
            User model if successful, None if otherwise
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                userSQL = """
                    SELECT user_id, username, email, full_name, created_at, last_active, preferences
                    FROM users.users
                    WHERE username = $1
                """
                result = await conn.fetchrow(userSQL, username)
                if result:
                    return User(
                        user_id=result['user_id'],
                        username=result['username'],
                        email=result['email'],
                        full_name=result['full_name'],
                        created_at=result['created_at'],
                        last_active=result['last_active'],
                        preferences=result['preferences']
                    )
                return None
        except Exception as e:
            self.logger.error(f"Failed to get user by username: {str(e)}")
            return None

    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a user

        Args:
            user_id: the user id string to update
            updates: a dictionary of fields to update

        Returns:
            boolean
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Convert Pydantic model to dict
                update_dict = updates

                # Prepare SQL update statement
                set_clause = ', '.join([f"{key} = ${i+1}" for i, key in enumerate(update_dict.keys())])
                values = list(update_dict.values())

                userUpdateSQL = f"""
                    UPDATE users.users
                    SET {set_clause}, last_active = NOW()
                    WHERE user_id = $1
                """
                values.insert(0, user_id)

                # execute update query
                result = await conn.execute(userUpdateSQL, *values)
                if result == "UPDATE 0":
                    self.logger.warning(f"User with id {user_id} does not exist.")
                    return False

                return result == "UPDATE 1"
        except Exception as e:
            self.logger.error(f"Failed to update user: {str(e)}")
            return False

    async def delete_user(self, user_id: str) -> bool:
        """ Delete a user and their credentials """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Delete from users table
                    userDeleteSQL = """
                        DELETE FROM users.users
                        WHERE user_id = $1
                    """
                    user_result = await conn.execute(userDeleteSQL, user_id)

                    # Delete credentials if they exist
                    credDeleteSQL = """
                        DELETE FROM security.credentials
                        WHERE user_id = $1
                    """
                    await conn.execute(credDeleteSQL, user_id)

                    # Delete password history
                    historyDeleteSQL = """
                        DELETE FROM security.password_history
                        WHERE user_id = $1
                    """
                    await conn.execute(historyDeleteSQL, user_id)

                    if user_result == "DELETE 0":
                        self.logger.warning(f"User with id {user_id} does not exist.")
                        return False

                    return True
        except Exception as e:
            self.logger.error(f"Failed to delete user: {str(e)}")
            return False

    async def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """ List users with pagination """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # prepare SQL select statement
                userListSQL = """
                    SELECT user_id, username, email, full_name, created_at, last_active, preferences
                    FROM users.users
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                """
                # execute select query
                results = await conn.fetch(userListSQL, limit, offset)
                if results:
                    return [User(
                        user_id=result['user_id'],
                        username=result['username'],
                        email=result['email'],
                        full_name=result['full_name'],
                        created_at=result['created_at'],
                        last_active=result['last_active'],
                        preferences=result['preferences']
                    ) for result in results]
                return []
        except Exception as e:
            self.logger.error(f"Failed to list users: {str(e)}")
            return False

    async def change_user_password(self, user_id: str, current_password: str, new_password: str,
                             ip_address: str, user_agent: str) -> Tuple[bool, str]:
        """
        Change a user's password

        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            from app.core.db.big_brother import BigBrother

            success, message = await BigBrother.change_password(
                user_id, current_password, new_password, ip_address, user_agent
            )

            return success, message

        except Exception as e:
            self.logger.error(f"Failed to change user password: {str(e)}")
            return False, f"Password change error: {str(e)}"

    # --------- MFA operations ---------
    async def setup_user_mfa(self, user_id: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Set up multi-factor authentication for a user

        Args:
            user_id: User ID
            username: Username

        Returns:
            Optional[Dict]: MFA setup information including QR code
        """
        try:
            from app.core.db.big_brother import BigBrother

            totp_setup = await BigBrother.setup_totp(user_id, username)

            if totp_setup:
                return {
                    "secret": totp_setup.secret,
                    "uri": totp_setup.uri,
                    "qr_code": totp_setup.qr_code
                }
            return None

        except Exception as e:
            self.logger.error(f"Failed to set up MFA: {str(e)}")
            return None

    async def enable_user_mfa(self, user_id: str, totp_secret: str, verification_code: str) -> bool:
        """
        Enable multi-factor authentication for a user

        Args:
            user_id: User ID
            totp_secret: TOTP secret
            verification_code: Verification code from TOTP app

        Returns:
            bool: Success status
        """
        try:
            from app.core.db.big_brother import BigBrother

            return await BigBrother.enable_totp(user_id, totp_secret, verification_code)

        except Exception as e:
            self.logger.error(f"Failed to enable MFA: {str(e)}")
            return False

    async def disable_user_mfa(self, user_id: str, password: str) -> bool:
        """
        Disable multi-factor authentication for a user

        Args:
            user_id: User ID
            password: Current password for verification

        Returns:
            bool: Success status
        """
        try:
            from app.core.db.big_brother import BigBrother

            return await BigBrother.disable_totp(user_id, password)

        except Exception as e:
            self.logger.error(f"Failed to disable MFA: {str(e)}")
            return False

    # ---------- password resets ----------
    async def request_password_reset(self, email: str, ip_address: str) -> Tuple[bool, str]:
        """
        Request a password reset

        Args:
            email: User email

        Returns:
            Tuple[bool, str]: (success, message or token)
        """
        try:
            from app.core.db.big_brother import BigBrother
            success, result = await BigBrother.create_password_reset_token(email, ip_address)
            return success, result
        except Exception as e:
            self.logger.error(f"Failed to request password reset: {str(e)}")
            return False, f"Password reset error: {str(e)}"

    async def reset_password(self, token: str, new_password: str) -> Tuple[bool, str]:
        """
        Reset password using a token

        Args:
            token: Password reset token
            new_password: New password

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            from app.core.db.big_brother import BigBrother
            return await BigBrother.reset_password_with_token(token, new_password)

        except Exception as e:
            self.logger.error(f"Failed to reset password: {str(e)}")
            return False, f"Password reset error: {str(e)}"

    # ========== Session operations ==========
    async def create_session(self, session: SessionCreate, ip_address: str = None, user_agent: str = None) -> Optional[Session]:
        """ Create a new session """
        try:
            # Generate a session id
            session_id = f"session_{secrets.token_hex(8)}"

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Convert Pydantic to dict
                session_dict = session.model_dump()

                # Extract specific fields
                user_id = session_dict.get('user_id')
                metadata = session_dict.get('metadata')

                sessionCreateSQL = """
                    INSERT INTO users.sessions
                    (session_id, user_id, metadata)
                    VALUES ($1, $2, $3)
                    RETURNING session_id, user_id, created_at, last_active, status, metadata
                """
                # Execute query
                result = await conn.fetchrow(sessionCreateSQL, session_id, user_id,
                                            json.dumps(metadata) if metadata else None)

                if result:
                    # Log session creation as security event if tracking info provided
                    if ip_address and user_agent and user_id:
                        from app.core.db.big_brother import BigBrother, SecurityEvent

                        await BigBrother.log_security_event(SecurityEvent(
                            event_type="session_created",
                            user_id=user_id,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            details={"session_id": session_id}
                        ))

                    return Session(
                        session_id=result['session_id'],
                        user_id=result['user_id'],
                        created_at=result['created_at'],
                        last_active=result['last_active'],
                        status=result['status'],
                        metadata=result['metadata']
                    )
                return None
        except Exception as e:
            self.logger.error(f"Failed to create session: {str(e)}")
            return None

    async def get_session(self, session_id: str) -> Optional[Session]:
        """ Get a session by ID """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                sessionSQL = """
                    SELECT session_id, user_id, created_at, last_active, status, metadata
                    FROM users.sessions
                    WHERE session_id = $1
                """
                result = await conn.fetchrow(sessionSQL, session_id)
                if result:
                    return Session(
                        session_id=result['session_id'],
                        user_id=result['user_id'],
                        created_at=result['created_at'],
                        last_active=result['last_active'],
                        status=result['status'],
                        metadata=result['metadata']
                    )
                return None
        except Exception as e:
            self.logger.error(f"Failed to get session: {str(e)}")
            return None

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """ Update a session """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Convert Pydantic model to dict
                update_dict = updates

                # Prepare SQL update statement
                set_clause = ', '.join([f"{key} = ${i+1}" for i, key in enumerate(update_dict.keys())])
                values = list(update_dict.values())

                sessionUpdateSQL = f"""
                    UPDATE users.sessions
                    SET {set_clause}, last_active = NOW()
                    WHERE session_id = $1
                """
                values.insert(0, session_id)

                # execute update query
                result = await conn.execute(sessionUpdateSQL, *values)
                if result == "UPDATE 0":
                    self.logger.warning(f"Session with id {session_id} does not exist.")
                    return False

                return result == "UPDATE 1"
        except Exception as e:
            self.logger.error(f"Failed to update session: {str(e)}")
            return False

    async def close_session(self, session_id: str) -> bool:
        """ Close a session (mark as inactive) """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                sessionCloseSQL = """
                    UPDATE users.sessions
                    SET status = 'inactive', last_active = NOW()
                    WHERE session_id = $1
                """
                result = await conn.execute(sessionCloseSQL, session_id)
                if result == "UPDATE 0":
                    self.logger.warning(f"Session with id {session_id} does not exist.")
                    return False

                return result == "UPDATE 1"
        except Exception as e:
            self.logger.error(f"Failed to close session: {str(e)}")
            return False

    async def list_user_sessions(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Session]:
        """ List sessions for a user """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                sessionListSQL = """
                    SELECT session_id, user_id, created_at, last_active, status, metadata
                    FROM users.sessions
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """
                results = await conn.fetch(sessionListSQL, user_id, limit, offset)
                if results:
                    return [Session(
                        session_id=result['session_id'],
                        user_id=result['user_id'],
                        created_at=result['created_at'],
                        last_active=result['last_active'],
                        status=result['status'],
                        metadata=result['metadata']
                    ) for result in results]
                return []
        except Exception as e:
            self.logger.error(f"Failed to list user sessions: {str(e)}")
            return None

    # ========== Conversation operations ==========
    async def create_conversation(self, conversation: ConversationCreate) -> Optional[Conversation]:
        """ Create a new conversation """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Convert Pydantic model to dict
                conversation_dict = conversation.dict(exclude_unset=True)

                # Prepare SQL insert statement
                columns = ', '.join(conversation_dict.keys())
                placeholders = ', '.join([f"${i+1}" for i in range(len(conversation_dict))])
                conversationInsertSQL = f"""
                    INSERT INTO users.conversations ({columns})
                    VALUES ({placeholders})
                    RETURNING conversation_id
                """
                result = await conn.fetchval(conversationInsertSQL, *conversation_dict.values())
                if not result:
                    self.logger.warning(f"Failed to create conversation.")
                    return None

                return Conversation(**conversation_dict, conversation_id=result)
        except Exception as e:
            self.logger.error(f"Failed to create conversation: {str(e)}")
            return None

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """ Get a conversation by ID """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                conversationSelectSQL = """
                    SELECT conversation_id, user_id, created_at, updated_at, metadata
                    FROM users.conversations
                    WHERE conversation_id = $1
                """
                result = await conn.fetchrow(conversationSelectSQL, conversation_id)
                if result:
                    return Conversation(**result)
                return None
        except Exception as e:
            self.logger.error(f"Failed to get conversation: {str(e)}")
            return None

    async def update_conversation(self, conversation_id: str, updates: Dict[str, Any]) -> bool:
        """ update a conversation """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL update statement
                conversationUpdateSQL = """
                    UPDATE users.conversations
                    SET {updates}
                    WHERE conversation_id = $1
                """
                # Format the updates
                updates = ', '.join([f"{key} = ${i+2}" for i, key in enumerate(updates.keys())])
                result = await conn.execute(conversationUpdateSQL.format(updates=updates), conversation_id, *updates.values())
                if result:
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Failed to update conversation: {str(e)}")
            return False

    async def delete_conversation(self, conversation_id: str) -> bool:
        """ Delete a converation """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL delete statement
                conversationDeleteSQL = """
                    DELETE FROM users.conversations
                    WHERE conversation_id = $1
                """
                result = await conn.execute(conversationDeleteSQL, conversation_id)
                if result:
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Failed to delete conversation: {str(e)}")
            return False

    async def list_session_conversation(self, session_id: str, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """ List conversation for a session """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL select statement
                conversationListSQL = """
                    SELECT conversation_id, user_id, created_at, updated_at, metadata
                    FROM users.conversations
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """
                # execute select query
                results = await conn.fetch(conversationListSQL, session_id, limit, offset)
                if results:
                    return [Conversation(**result) for result in results]
                return []
        except Exception as e:
            self.logger.error(f"Failed to list session conversations: {str(e)}")
            return None

    async def list_user_conversations(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """ List conversations for a user """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL select statement
                conversationListSQL = """
                    SELECT conversation_id, user_id, created_at, updated_at, metadata
                    FROM users.conversations
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """
                # execute select query
                results = await conn.fetch(conversationListSQL, user_id, limit, offset)
                if results:
                    return [Conversation(**result) for result in results]
                return []
        except Exception as e:
            self.logger.error(f"Failed to list user conversations: {str(e)}")
            return None

    # ========== Message operations ==========
    async def create_message(self, message: MessageCreate) -> Optional[Message]:
        """ Create a new message """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # generate a message id
                message_id = f"message_{secrets.token_hex(8)}"
                # Convert Pydantic model to dict
                message_dict = message.model_dump()

                # Extract specific fields
                conversation_id = message_dict.get('conversation_id')
                role = message_dict.get('role')
                content = message_dict.get('content')
                model_id = message_dict.get('model_id')
                request_id = message_dict.get('request_id')
                tokens = message_dict.get('tokens')
                metadata = message_dict.get('metadata')
                messageCreateSQL = """
                    INSERT INTO users.messages
                    (message_id, conversation_id, role, content, created_at, model_id, request_id, tokens, metadata)
                    VALUES ($1, $2, $3, $4, NOW(), $5, $6, $7, $8)
                    RETURNING message_id, conversation_id, role, content, created_at, model_id, request_id, tokens, metadata
                """
                # execute query
                result = await conn.fetch(messageCreateSQL, message_id, conversation_id, role, content, model_id, request_id, tokens, metadata)
                if result:
                    return Message(**result[0])
                return None
        except Exception as e:
            self.logger.error(f"Failed to create message: {str(e)}")
            return None

    async def get_message(self, message_id: str) -> Optional[Message]:
        """ Get a message by ID """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL select statement
                messageSelectSQL = """
                    SELECT message_id, conversation_id, role, content, created_at, model_id, request_id, tokens, metadata
                    FROM users.messages
                    WHERE message_id = $1
                """
                # execute select query
                result = await conn.fetch(messageSelectSQL, message_id)
                if result:
                    return Message(**result[0])
                return None
        except Exception as e:
            self.logger.error(f"Failed to get message: {str(e)}")
            return None

    async def update_message(self, message_id: str, updates: Dict[str, Any]) -> bool:
        """ update a message """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Convert Pydantic model to dict
                update_dict = updates

                # Prepare SQL update statement
                set_clause = ', '.join([f"{key} = ${i+1}" for i, key in enumerate(update_dict.keys())])
                values = list(update_dict.values())

                messageUpdateSQL = f"""
                    UPDATE users.messages
                    SET {set_clause}, created_at = NOW()
                    WHERE message_id = $1
                """
                values.insert(0, message_id)

                # execute update query
                result = await conn.execute(messageUpdateSQL, *values)
                if result == "UPDATE 0":
                    self.logger.warning(f"Message with id {message_id} does not exist.")
                    return False

                return result == "UPDATE 1"
        except Exception as e:
            self.logger.error(f"Failed to update message: {str(e)}")
            return False

    async def delete_message(self, message_id: str) -> bool:
        """ Delete a message"""
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL delete statement
                messageDeleteSQL = """
                    DELETE FROM users.messages
                    WHERE message_id = $1
                """
                # execute delete query
                result = await conn.execute(messageDeleteSQL, message_id)
                if result == "DELETE 0":
                    self.logger.warning(f"Message with id {message_id} does not exist.")
                    return False

                return result == "DELETE 1"
        except Exception as e:
            self.logger.error(f"Failed to delete message: {str(e)}")
            return False

    async def list_conversation_messages(self, conversation_id: str) -> Dict[str, Any]:
        """ Get a conversation with all its messages """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL select statement
                messageListSQL = """
                    SELECT message_id, conversation_id, role, content, created_at, model_id, request_id, tokens, metadata
                    FROM users.messages
                    WHERE conversation_id = $1
                    ORDER BY created_at ASC
                """
                # execute select query
                results = await conn.fetch(messageListSQL, conversation_id)
                if results:
                    return [Message(**result) for result in results]
                return []
        except Exception as e:
            self.logger.error(f"Failed to list conversation messages: {str(e)}")
            return None

    # ========== Advanced operations ==========
    async def get_conversation_with_messages(self, conversation_id: str) -> Dict[str, Any]:
        """ Get a conversation with all its messages """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL select statement for conversation
                conversationSQL = """
                    SELECT conversation_id, user_id, created_at, updated_at, metadata
                    FROM users.conversations
                    WHERE conversation_id = $1
                """
                # execute select query for conversation
                conversation_result = await conn.fetchrow(conversationSQL, conversation_id)
                if not conversation_result:
                    self.logger.warning(f"Conversation with id {conversation_id} does not exist.")
                    return None

                # Prepare SQL select statement for messages
                messageListSQL = """
                    SELECT message_id, conversation_id, role, content, created_at, model_id, request_id, tokens, metadata
                    FROM users.messages
                    WHERE conversation_id = $1
                    ORDER BY created_at ASC
                """
                # execute select query for messages
                message_results = await conn.fetch(messageListSQL, conversation_id)

                return {
                    "conversation": Conversation(**conversation_result),
                    "messages": [Message(**msg) for msg in message_results]
                }
        except Exception as e:
            self.logger.error(f"Failed to get conversation with messages: {str(e)}")
            return None

    async def get_conversation_message_count(self, conversation_id: str) -> int:
        """ Get the number of messages in a conversation """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL count statement
                messageCountSQL = """
                    SELECT COUNT(*) AS count
                    FROM users.messages
                    WHERE conversation_id = $1
                """
                # execute count query
                result = await conn.fetchrow(messageCountSQL, conversation_id)
                if result:
                    return result['count']
                return 0
        except Exception as e:
            self.logger.error(f"Failed to get conversation message count: {str(e)}")
            return 0

    async def search_messages(self, query: str, limit: int = 100, offset: int = 0) -> List[Message]:
        """ Serach for messages containing a query string """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Prepare SQL select statement
                messageSearchSQL = """
                    SELECT message_id, conversation_id, role, content, created_at, model_id, request_id, tokens, metadata
                    FROM users.messages
                    WHERE content ILIKE $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """
                # execute select query
                results = await conn.fetch(messageSearchSQL, f"%{query}%", limit, offset)
                if results:
                    return [Message(**result) for result in results]
                return []
        except Exception as e:
            self.logger.error(f"Failed to search messages: {str(e)}")
            return None

    async def lock_user_account(self, user_id: str, duration_minutes: int = 60,
                           reason: str = "Administrative lock") -> Tuple[bool, str]:
        """
        Lock a user account

        Args:
            user_id: User ID
            duration_minutes: Lock duration in minutes
            reason: Reason for locking

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            from app.core.db.big_brother import BigBrother

            success, message = await BigBrother.lock_account(
                user_id=user_id,
                duration_minutes=duration_minutes,
                reason=reason
            )

            return success, message
        except Exception as e:
            self.logger.error(f"Failed to lock user account: {str(e)}")
            return False, "Account lock failed due to an unexpected error."

    async def unlock_user_account(self, user_id: str, admin_id: str = None) -> Tuple[bool, str]:
        """
        Unlock a user account

        Args:
            user_id: User ID
            admin_id: Administrator ID performing the unlock (for audit)

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            from app.core.db.big_brother import BigBrother

            success, message = await BigBrother.unlock_account(
                user_id=user_id,
                admin_id=admin_id
            )

            return success, message
        except Exception as e:
            self.logger.error(f"Failed to unlock user account: {str(e)}")
            return False, "Account unlock failed due to an unexpected error."

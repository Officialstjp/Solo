"""
Module Name: app/core/db/models_db.py
Purpose: Database service for model registry operations
Params: None
History:
    Date            Notes
    2025-07-13      Initial implementation
"""

from typing import Dict, List, Optional, Any, Union
import json
import asyncpg
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.db.connection import get_connection_pool
from app.utils.logger import get_logger

# ===== Pydantic models ======

class ModelBase(BaseModel):
    """ Base model for model registry entires"""
    model_id: str
    name: str
    path: str
    format: str
    parameter_size: str
    quantization: Optional[str] = None
    context_length: Optional[int] = None
    file_size_mb: Optional[float] = None

class ModelCreate(ModelBase):
    """ Model for creating a new registry netry """
    metadata: Optional[Dict[str, Any]] = None

class ModelUpdate(BaseModel):
    """ Model for updating an existing model registry entry """
    name: Optional[str] = None
    path: Optional[str] = None
    format: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization: Optional[str] = None
    context_length: Optional[str] = None
    file_size_mb: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class Model(ModelBase):
    """ Complete model registry entry with all fields """
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: Optional[int] = None

class ModelUsage(BaseModel):
    """Model for recording model usage"""
    model_id: str
    usage_type: str
    tokens_generated: Optional[int] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

class ModelUsageStats(BaseModel):
    """Stats about model usage"""
    model_id: str
    usage_count: int
    total_tokens: int
    avg_tokens: float

class ModelResponse(BaseModel):
    """Response model for individual model queries"""
    model: Optional[Model] = None
    error: Optional[str] = None

class ModelsResponse(BaseModel):
    """Response model for listing models"""
    models: List[Model] = []
    count: int
    error: Optional[str] = None

class ModelUsageResponse(BaseModel):
    """Response model for model usage stats"""
    period: Dict[str, str]
    total_usage: int
    by_model: List[ModelUsageStats] = []
    by_type: List[Dict[str, Any]] = []
    hourly_pattern: List[Dict[str, Any]] = []
    error: Optional[str] = None

# ===== Database service =====

class ModelsDatabase:
    """
    Database service for model registry operations
    """

    def __init__(self):
        """ initialize the logger at __init__"""
        self.logger = get_logger("models_db")

    async def initialize(self):
        """ Initalize the DB, get connection_pool and check if schema exists"""
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # check if models schema exists
                schema_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = 'models')"
                )

                if not schema_exists:
                    self.logger.warning("Models schema doesn't exist, Some model operations may fail." )

                # check if model_registry table exists
                model_registry_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname = 'models' AND tablename = 'models')"
                )

                if not model_registry_exists:
                    self.logger.warning("models.models table doesnt exist. Model registry operations will be disabled")

                # Check if model_usage table exists
                # The model_usage table will be created when needed, so we don't need to check for it yet
                # Just log a warning for now
                self.logger.warning("model_usage table doesn't exist. Model usage tracking will be disabled.")

            self.logger.info("Models database service initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize models database service: {e}")
            return False

    async def register_model(self, model: ModelCreate) -> bool:
        """ Register a model in the model registry

        Args:
            model: ModelCreate with model data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert Pydantic model to dict for DB inseration
            model_dict = model.model_dump()

            # handle JSON serialization for metadata field
            if model_dict.get('metadata'):
                model_dict['metadata'] = json.dumps(model_dict['metadata'])

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # check if the model already exists
                existing = await conn.fetchval(
                    "SELECT 1 FROM models.models WHERE model_id = $1",
                    model.model_id
                )

                if existing:
                    # Update existing model
                    updates = []
                    values = []

                    for key, value in model_dict.items():
                        if key != 'model_id': # skip primary key
                            updates.append(f"{key} = ${len(values) + 2}")
                            values.append(value)

                    updates.append("updated_at = NOW()")

                    query = f"""
                        UPDATE models.model_registry
                        SET {', '.join(updates)}
                        WHERE model_id = $1
                    """

                    values.insert(0, model.model_id)

                    await conn.execute(query, *values)
                    self.logger.info(f"Updated model {model.name} ({model.model_id})")
                else:
                    # insert new model
                    columns = ", ".join(model_dict.keys())
                    placeholders = ", ".join([f"${i+1}" for i in range(len(model_dict))])

                    query = f"""
                        INSERT INTO models.models
                        ({columns}, created_at, updated_at)
                        VALUES ({placeholders}, NOW(), NOW())
                        """

                    values = list(model_dict.values())

                    await conn.execute(query, *values)
                    self.logger.info(f"Registered new model {model.name} ({model.model_id})")

                return True
        except Exception as e:
            self.logger.error(f"Failed to register model {model.name} ({model.model_id}): {e}")
            return False

    async def get_model(self, model_id: str) -> ModelResponse:
        """Get model information from the registry

        Args:
            model_id: Unique identifier for the model

        Returns:
            ModelResponse with model data or error
        """
        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                record = await conn.fetchrow("""
                    SELECT * FROM models.models
                    WHERE model_id = $1
                    """, model_id)

                if record:
                    model_data = dict(record)
                    if model_data.get('metadata'):
                        model_data['metadata'] = json.loads(model_data['metadata'])

                    model = Model(**model_data)
                    return ModelResponse(model=model)

                return ModelResponse(error=f"Model {model_id} not found")
        except Exception as e:
            self.logger.error(f"Failed to retrieve model {model_id}: {e}")
            return ModelResponse(error=str(e))

    async def list_models(self,
                          format: Optional[str] = None,
                          parameter_size: Optional[str] = None,
                          limit: int = 100) -> ModelsResponse:
        """ List models in the registry with optional filtering

        Args:
            format: filter by model format (optional)
            parameter_size: Filter by parameter size (optional)
            limit: Maximum number of models to return

        Returns:
            ModelsResponse with models list and count
        """
        try:
            query = "SELECT * FROM models.models"
            params = []

            # Add filters if provided
            filters = []
            if format:
                filters.append(f"format = ${len(params) + 1}")
                params.append(format)

            if parameter_size:
                filters.append(f"parameter_size = ${len(params) + 1}")
                params.append(parameter_size)

            if filters:
                query += " WHERE " + " AND ".join(filters)

            query += " ORDER BY created_at DESC"

            if limit:
                query += f" LIMIT ${len(params) + 1}"
                params.append(limit)

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch(query, *params)

                models = []
                for record in records:
                    model_data = dict(record)
                    # Parse metadata JSON
                    if model_data.get('metadata'):
                        model_data['metadata'] = json.loads(model_data['metadata'])
                    models.append(Model(**model_data))

                return ModelsResponse(
                    models=models,
                    count=len(models)
                )
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")
            return ModelsResponse(
                models=[],
                count=0,
                error=str(e)
            )

    async def delete_model(self, model_id: str) -> bool:
            """Delete a model from the registry

            Args:
                model_id: Unique identifier for the model

            Returns:
                bool: True if successful, False otherwise
            """
            try:
                pool = await get_connection_pool()
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        # Delete model usage records first (foreign key constraint)
                        await conn.execute(
                            "DELETE FROM models.model_usage WHERE model_id = $1",
                            model_id
                        )

                        # Delete from registry
                        result = await conn.execute(
                            "DELETE FROM models.models WHERE model_id = $1",
                            model_id
                        )

                        if "DELETE 0" in result:
                            self.logger.warning(f"Model {model_id} not found in registry")
                            return False

                        self.logger.info(f"Model {model_id} deleted from registry")
                        return True
            except Exception as e:
                self.logger.error(f"Failed to delete model {model_id}: {e}")
                return False

    async def record_model_usage(self, usage: ModelUsage) -> bool:
        """Record usage of a model

        Args:
            usage: ModelUsage with usage data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert Pydantic model to dict for DB insertion
            usage_dict = usage.model_dump()

            # Handle JSON serialization for details field
            if usage_dict.get('details'):
                usage_dict['details'] = json.dumps(usage_dict['details'])

            # Create a SQL query with columns and placeholders
            columns = ", ".join(usage_dict.keys())
            placeholders = ", ".join([f"${i+1}" for i in range(len(usage_dict))])

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Insert usage record
                query = f"""
                    INSERT INTO models.model_usage
                    ({columns}, timestamp)
                    VALUES ({placeholders}, NOW())
                """

                # Extract values in the same order as columns
                values = list(usage_dict.values())

                await conn.execute(query, *values)

                # Update last_used timestamp in registry
                await conn.execute("""
                    UPDATE models.model_registry
                    SET
                        last_used_at = NOW(),
                        usage_count = COALESCE(usage_count, 0) + 1
                    WHERE model_id = $1
                """, usage.model_id)

                self.logger.debug(f"Recorded usage of model {usage.model_id}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to record usage of model {usage.model_id}: {e}")
            return False

    async def get_model_usage_stats(self,
                                    model_id: Optional[str] = None,
                                    start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None) -> ModelUsageResponse:
        """Get usage statistics for models

        Args:
            model_id: Filter by model ID (optional)
            start_time: Start time for statistics (optional)
            end_time: End time for statistics (optional)

        Returns:
            ModelUsageResponse with usage statistics
        """
        try:
            if start_time is None:
                start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            if end_time is None:
                end_time = datetime.now()

            # Base query
            query_params = [start_time, end_time]
            model_filter = ""
            if model_id:
                model_filter = " AND model_id = $3"
                query_params.append(model_id)

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Get total usage count
                total_usage = await conn.fetchval(f"""
                    SELECT COUNT(*)
                    FROM models.model_usage
                    WHERE timestamp BETWEEN $1 AND $2{model_filter}
                """, *query_params)

                # Get usage by model
                usage_by_model_query = f"""
                    SELECT
                        model_id,
                        COUNT(*) as usage_count,
                        SUM(tokens_generated) as total_tokens,
                        AVG(tokens_generated) as avg_tokens
                    FROM models.model_usage
                    WHERE timestamp BETWEEN $1 AND $2{model_filter}
                    GROUP BY model_id
                    ORDER BY usage_count DESC
                """

                usage_by_model_records = await conn.fetch(usage_by_model_query, *query_params)

                # Get usage by type
                usage_by_type_query = f"""
                    SELECT
                        usage_type,
                        COUNT(*) as count
                    FROM models.model_usage
                    WHERE timestamp BETWEEN $1 AND $2{model_filter}
                    GROUP BY usage_type
                    ORDER BY count DESC
                """

                usage_by_type = await conn.fetch(usage_by_type_query, *query_params)

                # Hourly usage pattern
                hourly_usage_query = f"""
                    SELECT
                        EXTRACT(HOUR FROM timestamp) as hour,
                        COUNT(*) as count
                    FROM models.model_usage
                    WHERE timestamp BETWEEN $1 AND $2{model_filter}
                    GROUP BY hour
                    ORDER BY hour
                """

                hourly_usage = await conn.fetch(hourly_usage_query, *query_params)

                # Convert usage by model records to Pydantic models
                usage_by_model = []
                for record in usage_by_model_records:
                    usage_by_model.append(ModelUsageStats(**dict(record)))

                return ModelUsageResponse(
                    period={
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat()
                    },
                    total_usage=total_usage or 0,
                    by_model=usage_by_model,
                    by_type=[dict(record) for record in usage_by_type],
                    hourly_pattern=[dict(record) for record in hourly_usage]
                )
        except Exception as e:
            self.logger.error(f"Failed to get model usage statistics: {e}")
            return ModelUsageResponse(
                period={
                    "start": start_time.isoformat() if start_time else None,
                    "end": end_time.isoformat() if end_time else None
                },
                total_usage=0,
                error=str(e)
            )

    async def update_model(self, model_id: str, updates: ModelUpdate) -> ModelResponse:
        """Update model information in the registry

        Args:
            model_id: Unique identifier for the model
            updates: ModelUpdate with fields to update

        Returns:
            ModelResponse with updated model data or error
        """
        try:
            # Convert Pydantic model to dict for DB update
            updates_dict = updates.model_dump(exclude_unset=True)

            if not updates_dict:
                return ModelResponse(error="No updates provided")

            # Handle JSON serialization for metadata field
            if updates_dict.get('metadata'):
                updates_dict['metadata'] = json.dumps(updates_dict['metadata'])

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Check if model exists
                exists = await conn.fetchval(
                    "SELECT 1 FROM models.models WHERE model_id = $1",
                    model_id
                )

                if not exists:
                    return ModelResponse(error=f"Model {model_id} not found")

                # Create SQL update statement
                updates_list = []
                values = [model_id]  # First param is model_id

                for key, value in updates_dict.items():
                    updates_list.append(f"{key} = ${len(values) + 1}")
                    values.append(value)

                # Add updated_at timestamp
                updates_list.append("updated_at = NOW()")

                query = f"""
                    UPDATE models.model_registry
                    SET {', '.join(updates_list)}
                    WHERE model_id = $1
                """

                await conn.execute(query, *values)

                # Fetch the updated model
                record = await conn.fetchrow(
                    "SELECT * FROM models.models WHERE model_id = $1",
                    model_id
                )

                model_data = dict(record)
                # Parse metadata JSON
                if model_data.get('metadata'):
                    model_data['metadata'] = json.loads(model_data['metadata'])

                return ModelResponse(model=Model(**model_data))
        except Exception as e:
            self.logger.error(f"Failed to update model {model_id}: {e}")
            return ModelResponse(error=str(e))

# Writing the docker-compose.yml

## Services
``` yml
services:
    db:
        # Configuration for postgres container
```
Each service defines a container. -> service db - container db

## Container Configuration
``` yml
image: pgvector/pgvector:pg17
container_name: solo_postgres
```
- image: The Docker image to use (pgvector with PostgreSQL 17)
- container_name: A friendly name for the container

## Environment variables
``` yml
environment:
    POSTGRES_USER: ${POSTGRES_USER:-solo_app}
    POSTGRES_PASSWORD: ${POSTGRES_PASSOWRD:-Start1234}
    POSTGRES_DB: ${POSTGRES_DB:-solo}
```
- Sets container environment variables
- The `${Variable:-default}` syntax means "use the environment variable if it exists, otherwise use the default value"
- These environment variables configure PostgreSQL itself

## Volumes:
``` yml
volumes:
- solo_pg_data:/var/lib/postgresql/data
- ./scripts/SQL:/docker-entrypoint-initdb.d
```
- Maps storage between host and container
- `solo_pg_data:/var/lib/postgresql/data:` A named volume for database storage
- `./scripts/SQL:/docker-entrypoint-initddb.d` Maps qsl scripts to the containers initialization directory
Files in this directory are executed alphabetically during container initialization

## Network settings
``` yml
ports:
- "${POSTGRES_PORT:-5432}:5432
networks:
- solo_network
```
- ports: Maps container ports to host ports
- netowrks: Places the container on a specific network

## Health Checks
``` yml
healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:solo_app} -d ${POSTGRES_DB:-solo}"]
    interval: 10s
    timeout: 5s
    retries: 3
```
Defines how docker should check if the container is healthy:
- Runs the specified command every 10 seconds
- Considers the container unhealthy after 3 failed checks

## Restart policy
```yml
restart: unless-stopped
```
Automatically restarts the container if it crashes or when Docker restarts, unless you explicitly stop it.

Resource Limits:
``` yml
deploy:
    resources:
        limits:
            cpus: '2'
            memory: 4G
```
Prevent the container from using more than 2 CPU cores and 4GB of memory.

##Network and Volumes Definition
```yml
networks:
    solo_network:
        driver: bridge

volumes:
    solo_pg_data:
        driver: local
```

- `networks:` Defines the custom networks for container communication
- `volumes:` Defines named volumes for persistent data storage

# Running docker

1. Install Docker Compose (if not already installed with Docker Desktop)

2. Create a docker-compose.yml file in your project root with the configuration

3. Create a .env file with your environment variables:
```
POSTGRES_USER=solo_app
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=solo
POSTGRES_PORT=5432
```

4. Start your containers:
```
docker-compose up -d
```
The -d flag runs containers in the background (detached mode)

5. Check container status:
```
docker-compose ps
```

6. View logs:
```
docker-compose logs -f db
```
The -f flag follows the logs in real-time

7. Stop containers:
```
docker-compose down
```
This stops and removes containers but preserves volumes

8. Remove everything including volumes:
```
docker-compose down -v
```

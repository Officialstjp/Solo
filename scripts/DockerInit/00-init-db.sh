#!/bin/bash
# init-db.sh - Environment variable substitution for SQL scripts
# Purpose   : Substitutes environment variables in SQL scripts before execution
# History   :
#   Date          Notes
#   07.05.2025    Initial version

set -e

# Define PostgreSQL passwords either from environment or with defaults
# Method 1: Using envsubst (environment variable substitution)
# First, process SQL files with envsubst to replace variables
echo "Processing SQL files with environment variable substitution..."
for f in /etc/postgresql/init-scripts/*.sql; do
  echo "Processing $f file..."

  # Create a temporary file with variables substituted
  tempfile=$(mktemp)
  export POSTGRES_APPPASSWORD="'${POSTGRES_APPPASSWORD:-AppUserPwd123}'"
  export POSTGRES_ADMPASSWORD="'${POSTGRES_ADMPASSWORD:-AdminPwd456}'"

  envsubst < "$f" > "$tempfile"

  # Execute the processed SQL file
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$tempfile"

  # Clean up the temporary file
  rm "$tempfile"

  # For security, unset the variables after use
  unset POSTGRES_APPPASSWORD
  unset POSTGRES_ADMPASSWORD
done

# Alternative Method 2: Using PostgreSQL's variable substitution
# Uncomment to use this approach instead
# echo "Processing SQL files with PostgreSQL variable substitution..."
# for f in /docker-entrypoint-initdb.d/*.sql; do
#   echo "Processing $f file..."
#   psql -v ON_ERROR_STOP=1 \
#        -v app_password="'${POSTGRES_APPPASSWORD:-AppUserPwd123}'" \
#        -v adm_password="'${POSTGRES_ADMPASSWORD:-AdminPwd456}'" \
#        -U "$POSTGRES_USER" \
#        -d "$POSTGRES_DB" \
#        -f "$f"
# done

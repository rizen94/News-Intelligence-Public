#!/bin/bash
# Setup NAS Database - Creates database and user if needed
# This script helps set up the NAS database for the first time

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}NAS Database Setup Script${NC}"
echo "=============================="
echo ""

# Configuration
NAS_HOST="${DB_HOST:-192.168.93.100}"
NAS_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-news_intelligence}"
DB_USER="${DB_USER:-newsapp}"
DB_PASSWORD="${DB_PASSWORD:-newsapp_password}"

echo "This script will help set up the NAS database."
echo ""
echo "You'll need PostgreSQL admin credentials to:"
echo "  • Create database '${DB_NAME}'"
echo "  • Create user '${DB_USER}'"
echo "  • Grant permissions"
echo ""

read -p "Do you have PostgreSQL admin credentials? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Please get admin credentials from NAS web interface first.${NC}"
    echo "Access: http://${NAS_HOST}:8181"
    exit 0
fi

echo ""
read -p "PostgreSQL admin username (default: postgres): " ADMIN_USER
ADMIN_USER="${ADMIN_USER:-postgres}"

read -sp "PostgreSQL admin password: " ADMIN_PASSWORD
echo ""

echo ""
echo -e "${BLUE}Testing admin connection...${NC}"
export PGPASSWORD="$ADMIN_PASSWORD"

if ! psql -h "$NAS_HOST" -U "$ADMIN_USER" -d postgres -p "$NAS_PORT" -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}❌ Cannot connect with admin credentials${NC}"
    echo "Please verify:"
    echo "  1. Admin username is correct"
    echo "  2. Admin password is correct"
    echo "  3. PostgreSQL is running on NAS"
    echo "  4. Network connectivity to NAS"
    exit 1
fi

echo -e "${GREEN}✅ Admin connection successful${NC}"
echo ""

# Check if database exists
echo -e "${BLUE}Checking if database '${DB_NAME}' exists...${NC}"
DB_EXISTS=$(psql -h "$NAS_HOST" -U "$ADMIN_USER" -d postgres -p "$NAS_PORT" -t -c "
    SELECT COUNT(*) FROM pg_database WHERE datname = '${DB_NAME}';
" 2>/dev/null | tr -d ' ')

if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${YELLOW}⚠️  Database '${DB_NAME}' already exists${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
else
    echo -e "${BLUE}Creating database '${DB_NAME}'...${NC}"
    psql -h "$NAS_HOST" -U "$ADMIN_USER" -d postgres -p "$NAS_PORT" <<EOF
CREATE DATABASE ${DB_NAME}
    WITH OWNER = ${ADMIN_USER}
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;
EOF
    echo -e "${GREEN}✅ Database created${NC}"
fi

# Check if user exists
echo ""
echo -e "${BLUE}Checking if user '${DB_USER}' exists...${NC}"
USER_EXISTS=$(psql -h "$NAS_HOST" -U "$ADMIN_USER" -d postgres -p "$NAS_PORT" -t -c "
    SELECT COUNT(*) FROM pg_user WHERE usename = '${DB_USER}';
" 2>/dev/null | tr -d ' ')

if [ "$USER_EXISTS" = "1" ]; then
    echo -e "${YELLOW}⚠️  User '${DB_USER}' already exists${NC}"
    read -p "Update password? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Updating password for user '${DB_USER}'...${NC}"
        psql -h "$NAS_HOST" -U "$ADMIN_USER" -d postgres -p "$NAS_PORT" <<EOF
ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
EOF
        echo -e "${GREEN}✅ Password updated${NC}"
    fi
else
    echo -e "${BLUE}Creating user '${DB_USER}'...${NC}"
    psql -h "$NAS_HOST" -U "$ADMIN_USER" -d postgres -p "$NAS_PORT" <<EOF
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
EOF
    echo -e "${GREEN}✅ User created${NC}"
fi

# Grant permissions
echo ""
echo -e "${BLUE}Granting permissions...${NC}"
psql -h "$NAS_HOST" -U "$ADMIN_USER" -d "$DB_NAME" -p "$NAS_PORT" <<EOF
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
EOF
echo -e "${GREEN}✅ Permissions granted${NC}"

# Test connection
echo ""
echo -e "${BLUE}Testing connection with new credentials...${NC}"
export PGPASSWORD="$DB_PASSWORD"
if psql -h "$NAS_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$NAS_PORT" -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Connection successful!${NC}"
    echo ""
    echo -e "${GREEN}Database setup complete!${NC}"
    echo ""
    echo "You can now run the schema migration:"
    echo "  ./scripts/migrate_schema_to_nas.sh"
    echo ""
else
    echo -e "${RED}❌ Connection test failed${NC}"
    echo "Please check the credentials and try again"
    exit 1
fi


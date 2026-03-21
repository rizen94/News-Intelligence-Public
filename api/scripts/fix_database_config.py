#!/usr/bin/env python3
"""
Database Configuration Fix Script for News Intelligence System v3.0
Fixes database configuration mismatches and ensures consistency
"""

import logging
import sys
from pathlib import Path

# Add the API directory to the path
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fix_database_config_files():
    """Fix database configuration files to use consistent settings"""
    logger.info("Fixing database configuration files...")

    # Configuration to use
    config = {
        "host": "news-intelligence-postgres",
        "database": "news_intelligence",
        "user": "newsapp",
        "password": "newsapp_password",
        "port": "5432",
    }

    # Fix database.py
    try:
        database_py_path = api_dir / "config" / "database.py"
        if database_py_path.exists():
            logger.info("Updating database.py...")
            content = database_py_path.read_text()

            # Replace host configuration
            content = content.replace('"news-system-postgres"', f'"{config["host"]}"')
            content = content.replace('"newsintelligence"', f'"{config["database"]}"')
            content = content.replace('"Database@NEWSINT2025"', f'"{config["password"]}"')

            database_py_path.write_text(content)
            logger.info("✅ database.py updated")
        else:
            logger.warning("database.py not found")
    except Exception as e:
        logger.error(f"Failed to update database.py: {e}")

    # Fix robust_database.py
    try:
        robust_db_path = api_dir / "config" / "robust_database.py"
        if robust_db_path.exists():
            logger.info("Updating robust_database.py...")
            content = robust_db_path.read_text()

            # Replace host configuration
            content = content.replace("'postgres'", f"'{config['host']}'")
            content = content.replace("'news_system'", f"'{config['database']}'")
            content = content.replace("'Database@NEWSINT2025'", f"'{config['password']}'")

            robust_db_path.write_text(content)
            logger.info("✅ robust_database.py updated")
        else:
            logger.warning("robust_database.py not found")
    except Exception as e:
        logger.error(f"Failed to update robust_database.py: {e}")

    # Fix connection.py
    try:
        connection_py_path = api_dir / "database" / "connection.py"
        if connection_py_path.exists():
            logger.info("Updating connection.py...")
            content = connection_py_path.read_text()

            # Replace host configuration
            content = content.replace('"news-system-postgres"', f'"{config["host"]}"')
            content = content.replace('"newsintelligence"', f'"{config["database"]}"')
            content = content.replace('"Database@NEWSINT2025"', f'"{config["password"]}"')

            connection_py_path.write_text(content)
            logger.info("✅ connection.py updated")
        else:
            logger.warning("connection.py not found")
    except Exception as e:
        logger.error(f"Failed to update connection.py: {e}")


def update_docker_compose():
    """Update docker-compose.yml to ensure consistent configuration"""
    logger.info("Checking docker-compose.yml configuration...")

    try:
        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        if compose_path.exists():
            content = compose_path.read_text()

            # Check if configuration is already correct
            if "news-intelligence-postgres" in content and "newsapp_password" in content:
                logger.info("✅ docker-compose.yml already has correct configuration")
                return True

            logger.info("Updating docker-compose.yml...")

            # Replace postgres service name
            content = content.replace("postgres:", "news-intelligence-postgres:")
            content = content.replace(
                "container_name: postgres", "container_name: news-intelligence-postgres"
            )
            content = content.replace("@postgres:", "@news-intelligence-postgres:")

            # Ensure correct password
            content = content.replace(
                "POSTGRES_PASSWORD: Database@NEWSINT2025", "POSTGRES_PASSWORD: newsapp_password"
            )

            compose_path.write_text(content)
            logger.info("✅ docker-compose.yml updated")
            return True
        else:
            logger.warning("docker-compose.yml not found")
            return False
    except Exception as e:
        logger.error(f"Failed to update docker-compose.yml: {e}")
        return False


def create_environment_file():
    """Create a .env file with correct database configuration"""
    logger.info("Creating .env file...")

    try:
        env_path = Path(__file__).parent.parent.parent / ".env"

        env_content = """# News Intelligence System v3.0 - Environment Configuration
# Database Configuration
DB_HOST=news-intelligence-postgres
DB_NAME=news_intelligence
DB_USER=newsapp
DB_PASSWORD=newsapp_password
DB_PORT=5432

# Database URL for SQLAlchemy
DATABASE_URL=postgresql://newsapp:newsapp_password@news-intelligence-postgres:5432/news_intelligence

# Redis Configuration
REDIS_URL=redis://news-intelligence-redis:6379/0

# Application Configuration
ENVIRONMENT=production
LOG_LEVEL=info
"""

        env_path.write_text(env_content)
        logger.info("✅ .env file created")
        return True
    except Exception as e:
        logger.error(f"Failed to create .env file: {e}")
        return False


def verify_configuration():
    """Verify that all configurations are consistent"""
    logger.info("Verifying configuration consistency...")

    issues = []

    # Check docker-compose.yml
    try:
        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        if compose_path.exists():
            content = compose_path.read_text()
            if "news-intelligence-postgres" not in content:
                issues.append("docker-compose.yml: postgres service name incorrect")
            if "newsapp_password" not in content:
                issues.append("docker-compose.yml: password incorrect")
        else:
            issues.append("docker-compose.yml: file not found")
    except Exception as e:
        issues.append(f"docker-compose.yml: {e}")

    # Check unified_database.py
    try:
        unified_path = api_dir / "config" / "unified_database.py"
        if unified_path.exists():
            content = unified_path.read_text()
            if "news-intelligence-postgres" not in content:
                issues.append("unified_database.py: host configuration incorrect")
        else:
            issues.append("unified_database.py: file not found")
    except Exception as e:
        issues.append(f"unified_database.py: {e}")

    if issues:
        logger.error("Configuration issues found:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False
    else:
        logger.info("✅ All configurations are consistent")
        return True


def main():
    """Main fix function"""
    logger.info("Starting database configuration fix...")

    # Fix configuration files
    fix_database_config_files()

    # Update docker-compose.yml
    docker_updated = update_docker_compose()

    # Create .env file
    env_created = create_environment_file()

    # Verify configuration
    config_verified = verify_configuration()

    # Summary
    logger.info("=" * 50)
    logger.info("FIX SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Docker Compose updated: {'YES' if docker_updated else 'NO'}")
    logger.info(f"Environment file created: {'YES' if env_created else 'NO'}")
    logger.info(f"Configuration verified: {'YES' if config_verified else 'NO'}")

    if config_verified:
        logger.info("✅ Database configuration fix completed successfully")
        logger.info("Next steps:")
        logger.info("1. Restart the Docker containers: docker-compose down && docker-compose up -d")
        logger.info(
            "2. Test the database connection: python api/scripts/test_database_connection.py"
        )
        return 0
    else:
        logger.error("❌ Database configuration fix has issues")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

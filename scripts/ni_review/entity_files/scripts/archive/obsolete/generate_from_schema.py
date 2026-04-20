#!/usr/bin/env python3
"""
Schema-Driven Code Generator
Generates database migrations, API models, and frontend types from unified schema
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

def load_schema():
    """Load the unified schema definition"""
    schema_path = Path("schema/unified_schema.json")
    with open(schema_path, 'r') as f:
        return json.load(f)

def generate_database_migration(schema):
    """Generate database migration SQL from schema"""
    migration_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    migration_name = f"unified_schema_v{schema['version'].replace('.', '_')}"
    
    sql_parts = [
        f"-- Migration: {migration_name}",
        f"-- Generated: {datetime.now().isoformat()}",
        f"-- Version: {schema['version']}",
        "",
        "-- Drop existing tables if they exist (in reverse dependency order)",
        "DROP TABLE IF EXISTS storylines CASCADE;",
        "DROP TABLE IF EXISTS articles CASCADE;",
        "DROP TABLE IF EXISTS rss_feeds CASCADE;",
        "",
        "-- Create tables"
    ]
    
    # Create RSS feeds table first (no dependencies)
    if "rss_feeds" in schema["tables"]:
        table = schema["tables"]["rss_feeds"]
        sql_parts.append(f"CREATE TABLE rss_feeds (")
        
        column_defs = []
        for col_name, col_def in table["columns"].items():
            col_sql = f"    {col_name} {col_def['type']}"
            if not col_def.get("nullable", True):
                col_sql += " NOT NULL"
            if "default" in col_def:
                col_sql += f" DEFAULT {col_def['default']}"
            if col_def.get("primary_key"):
                col_sql += " PRIMARY KEY"
            if col_def.get("auto_increment"):
                col_sql += " GENERATED ALWAYS AS IDENTITY"
            column_defs.append(col_sql)
        
        sql_parts.append(",\n".join(column_defs))
        sql_parts.append(");")
        sql_parts.append("")
    
    # Create articles table
    if "articles" in schema["tables"]:
        table = schema["tables"]["articles"]
        sql_parts.append(f"CREATE TABLE articles (")
        
        column_defs = []
        for col_name, col_def in table["columns"].items():
            col_sql = f"    {col_name} {col_def['type']}"
            if not col_def.get("nullable", True):
                col_sql += " NOT NULL"
            if "default" in col_def:
                col_sql += f" DEFAULT {col_def['default']}"
            if col_def.get("primary_key"):
                col_sql += " PRIMARY KEY"
            if col_def.get("auto_increment"):
                col_sql += " GENERATED ALWAYS AS IDENTITY"
            column_defs.append(col_sql)
        
        sql_parts.append(",\n".join(column_defs))
        sql_parts.append(");")
        sql_parts.append("")
    
    # Create storylines table
    if "storylines" in schema["tables"]:
        table = schema["tables"]["storylines"]
        sql_parts.append(f"CREATE TABLE storylines (")
        
        column_defs = []
        for col_name, col_def in table["columns"].items():
            col_sql = f"    {col_name} {col_def['type']}"
            if not col_def.get("nullable", True):
                col_sql += " NOT NULL"
            if "default" in col_def:
                col_sql += f" DEFAULT {col_def['default']}"
            if col_def.get("primary_key"):
                col_sql += " PRIMARY KEY"
            if col_def.get("auto_increment"):
                col_sql += " GENERATED ALWAYS AS IDENTITY"
            column_defs.append(col_sql)
        
        sql_parts.append(",\n".join(column_defs))
        sql_parts.append(");")
        sql_parts.append("")
    
    # Add indexes
    for table_name, table in schema["tables"].items():
        if "indexes" in table:
            for index in table["indexes"]:
                columns = ", ".join(index["columns"])
                sql_parts.append(f"CREATE INDEX {index['name']} ON {table_name} ({columns});")
    
    # Add foreign key constraints
    for table_name, table in schema["tables"].items():
        for col_name, col_def in table["columns"].items():
            if "foreign_key" in col_def:
                fk_table, fk_column = col_def["foreign_key"].split(".")
                sql_parts.append(f"ALTER TABLE {table_name} ADD CONSTRAINT fk_{table_name}_{col_name} FOREIGN KEY ({col_name}) REFERENCES {fk_table}({fk_column});")
    
    # Insert sample data
    sql_parts.extend([
        "",
        "-- Insert sample RSS feed",
        "INSERT INTO rss_feeds (name, url, is_active, fetch_interval) VALUES",
        "('Hacker News Test Feed', 'https://hnrss.org/frontpage', true, 300);",
        "",
        "-- Insert sample articles",
        "INSERT INTO articles (title, content, url, published_at, source, category, status, tags, quality_score, language, word_count, reading_time) VALUES",
        "('Sample Article 1', 'This is sample content for testing.', 'https://example.com/1', NOW(), 'Hacker News Test Feed', 'Technology', 'processed', '[\"tech\", \"sample\"]', 0.8, 'en', 50, 2),",
        "('Sample Article 2', 'Another sample article for testing.', 'https://example.com/2', NOW(), 'Hacker News Test Feed', 'Technology', 'processed', '[\"tech\", \"sample\"]', 0.7, 'en', 75, 3);"
    ])
    
    # Write migration file
    migration_file = f"api/database/migrations/{migration_id}_{migration_name}.sql"
    os.makedirs(os.path.dirname(migration_file), exist_ok=True)
    
    with open(migration_file, 'w') as f:
        f.write("\n".join(sql_parts))
    
    print(f"✅ Generated database migration: {migration_file}")
    return migration_file

def generate_api_models(schema):
    """Generate Pydantic models for API from schema"""
    models = []
    
    for model_name, definition in schema["definitions"].items():
        if model_name in ["ArticleStats", "RSSStats"]:
            continue  # Skip stats models for now
            
        model_code = [
            f"class {model_name}(BaseModel):",
            f'    """{definition.get("description", f"{model_name} model")}"""',
            ""
        ]
        
        for prop_name, prop_def in definition["properties"].items():
            # Map JSON schema types to Python types
            py_type = "str"
            if prop_def["type"] == "integer":
                py_type = "int"
            elif prop_def["type"] == "number":
                py_type = "float"
            elif prop_def["type"] == "boolean":
                py_type = "bool"
            elif prop_def["type"] == "array":
                py_type = "List[str]"
            elif prop_def["type"] == "object":
                py_type = "Dict[str, Any]"
            elif prop_def["type"] == "string" and prop_def.get("format") == "date-time":
                py_type = "datetime"
            
            # Handle optional fields
            if prop_name not in definition.get("required", []):
                py_type = f"Optional[{py_type}]"
            
            # Add field with description
            description = prop_def.get("description", "")
            if description:
                model_code.append(f'    {prop_name}: {py_type} = Field(..., description="{description}")')
            else:
                model_code.append(f'    {prop_name}: {py_type}')
        
        models.append("\n".join(model_code))
    
    # Generate the complete models file
    models_file = "api/schemas/generated_models.py"
    os.makedirs(os.path.dirname(models_file), exist_ok=True)
    
    full_content = [
        '"""',
        'Generated API Models from Unified Schema',
        f'Version: {schema["version"]}',
        f'Generated: {datetime.now().isoformat()}',
        '"""',
        "",
        "from pydantic import BaseModel, Field",
        "from typing import Optional, List, Dict, Any",
        "from datetime import datetime",
        "",
        *models
    ]
    
    with open(models_file, 'w') as f:
        f.write("\n".join(full_content))
    
    print(f"✅ Generated API models: {models_file}")
    return models_file

def generate_frontend_types(schema):
    """Generate TypeScript types for frontend from schema"""
    types = []
    
    for type_name, definition in schema["definitions"].items():
        if type_name in ["ArticleStats", "RSSStats"]:
            continue  # Skip stats types for now
            
        type_code = [
            f"export interface {type_name} {{"
        ]
        
        for prop_name, prop_def in definition["properties"].items():
            # Map JSON schema types to TypeScript types
            ts_type = "string"
            if prop_def["type"] == "integer":
                ts_type = "number"
            elif prop_def["type"] == "number":
                ts_type = "number"
            elif prop_def["type"] == "boolean":
                ts_type = "boolean"
            elif prop_def["type"] == "array":
                ts_type = "string[]"
            elif prop_def["type"] == "object":
                ts_type = "Record<string, any>"
            elif prop_def["type"] == "string" and prop_def.get("format") == "date-time":
                ts_type = "string"  # ISO date string
            
            # Handle optional fields
            if prop_name not in definition.get("required", []):
                ts_type += "?"
            
            type_code.append(f"  {prop_name}: {ts_type};")
        
        type_code.append("}")
        types.append("\n".join(type_code))
    
    # Generate the complete types file
    types_file = "web/src/types/generated.ts"
    os.makedirs(os.path.dirname(types_file), exist_ok=True)
    
    full_content = [
        '/*',
        ' * Generated TypeScript Types from Unified Schema',
        f' * Version: {schema["version"]}',
        f' * Generated: {datetime.now().isoformat()}',
        ' */',
        "",
        *types
    ]
    
    with open(types_file, 'w') as f:
        f.write("\n".join(full_content))
    
    print(f"✅ Generated frontend types: {types_file}")
    return types_file

def generate_api_routes(schema):
    """Generate API route stubs from schema"""
    routes = []
    
    for endpoint_name, endpoint in schema["api_endpoints"].items():
        routes.append(f"# {endpoint_name.upper()} ROUTES")
        routes.append(f"# Base path: {endpoint['base_path']}")
        routes.append("")
        
        for op_name, operation in endpoint["operations"].items():
            routes.append(f"@router.{operation['method'].lower()}(\"{operation['path']}\")")
            routes.append(f"async def {op_name}_{endpoint_name}():")
            routes.append(f'    """{operation["description"]}"""')
            routes.append("    # TODO: Implement from schema")
            routes.append("    pass")
            routes.append("")
    
    # Write routes file
    routes_file = "api/routes/generated_routes.py"
    os.makedirs(os.path.dirname(routes_file), exist_ok=True)
    
    full_content = [
        '"""',
        'Generated API Routes from Unified Schema',
        f'Version: {schema["version"]}',
        f'Generated: {datetime.now().isoformat()}',
        '"""',
        "",
        "from fastapi import APIRouter",
        "",
        "router = APIRouter()",
        "",
        *routes
    ]
    
    with open(routes_file, 'w') as f:
        f.write("\n".join(full_content))
    
    print(f"✅ Generated API routes: {routes_file}")
    return routes_file

def main():
    """Main generation function"""
    print("🚀 Generating code from unified schema...")
    print("=" * 50)
    
    try:
        schema = load_schema()
        print(f"📋 Loaded schema version {schema['version']}")
        
        # Generate all components
        migration_file = generate_database_migration(schema)
        models_file = generate_api_models(schema)
        types_file = generate_frontend_types(schema)
        routes_file = generate_api_routes(schema)
        
        print("\n✅ Code generation complete!")
        print(f"📁 Files generated:")
        print(f"  - Database: {migration_file}")
        print(f"  - API Models: {models_file}")
        print(f"  - Frontend Types: {types_file}")
        print(f"  - API Routes: {routes_file}")
        
        print(f"\n🎯 Next steps:")
        print(f"  1. Run the database migration")
        print(f"  2. Update API imports to use generated models")
        print(f"  3. Update frontend to use generated types")
        print(f"  4. Implement the generated route stubs")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

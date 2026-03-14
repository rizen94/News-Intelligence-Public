#!/usr/bin/env python3
"""
Intelligence Database Management Script for News Intelligence System v2.1.0
Handles database schema updates, status management, and system configuration
"""

import os
import sys
import argparse
import psycopg2
import logging
from datetime import datetime
from typing import Dict, List

# Add the project root to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(project_root)

# Import centralized path configuration
from api.config.paths import PROJECT_ROOT, MIGRATIONS_DIR

try:
    from smart_article_pruner import SmartArticlePruner
except ImportError:
    SmartArticlePruner = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntelligenceDatabaseManager:
    """Manages the intelligence system database schema and operations."""
    
    def __init__(self, db_config: Dict = None):
        """Initialize the database manager. Uses shared DB config when db_config is None."""
        if db_config is None:
            import sys
            _api = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if _api not in sys.path:
                sys.path.insert(0, _api)
            from shared.database.connection import get_db_config
            db_config = get_db_config()
            db_config = {**db_config, "connect_timeout": 10, "statement_timeout": 30000}
        self.db_config = db_config
        
    def get_db_connection(self):
        """Get database connection from shared pool."""
        from shared.database.connection import get_db_connection as _get_conn
        conn = _get_conn()
        conn.autocommit = False
        return conn
    
    def update_database_schema(self, schema_file: str = None) -> bool:
        """Update the database schema for the intelligence system."""
        try:
            if not schema_file:
                # Try to find the latest schema file in migrations directory
                schema_file = os.path.join(MIGRATIONS_DIR, '001_base_schema.sql')
                
                if not os.path.exists(schema_file):
                    # Fallback to any .sql file in migrations
                    sql_files = [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql')]
                    if sql_files:
                        schema_file = os.path.join(MIGRATIONS_DIR, sorted(sql_files)[-1])
                    else:
                        logger.error(f"No schema files found in {MIGRATIONS_DIR}")
                        return False
            
            if not os.path.exists(schema_file):
                logger.error(f"Schema file not found: {schema_file}")
                return False
            
            logger.info(f"Updating database schema from: {schema_file}")
            
            # Read the schema file
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Execute the schema update
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Split the SQL into individual statements
            statements = schema_sql.split(';')
            
            for statement in statements:
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        cursor.execute(statement)
                        logger.debug(f"Executed: {statement[:100]}...")
                    except Exception as e:
                        logger.warning(f"Statement failed (continuing): {e}")
                        logger.debug(f"Failed statement: {statement}")
            
            # Commit changes
            conn.commit()
            logger.info("Database schema updated successfully!")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating database schema: {e}")
            if 'conn' in locals():
                conn.rollback()
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if new schema tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN (
                    'processed_articles',
                    'rag_context_requests',
                    'rag_research_topics',
                    'cleanup_protection_rules'
                )
            """)
            new_tables = [row[0] for row in cursor.fetchall()]
            
            # Check if new columns exist in articles table
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'articles' 
                AND column_name IN (
                    'processing_status',
                    'rag_keep_longer',
                    'rag_context_needed',
                    'rag_priority'
                )
            """)
            new_columns = [row[0] for row in cursor.fetchall()]
            
            # Get basic article counts
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN processing_status = 'raw' THEN 1 END) as raw_count,
                    COUNT(CASE WHEN processing_status = 'processing' THEN 1 END) as processing_count,
                    COUNT(CASE WHEN processing_status = 'ml_processed' THEN 1 END) as processed_count,
                    COUNT(CASE WHEN rag_keep_longer = TRUE THEN 1 END) as rag_keep_longer_count,
                    COUNT(CASE WHEN rag_context_needed = TRUE THEN 1 END) as rag_context_needed_count
                FROM articles
            """)
            status_counts = cursor.fetchone()
            
            return {
                'schema_status': {
                    'new_tables_exist': len(new_tables),
                    'new_tables': new_tables,
                    'new_columns_exist': len(new_columns),
                    'new_columns': new_columns,
                    'schema_up_to_date': len(new_tables) >= 4 and len(new_columns) >= 4
                },
                'article_status': {
                    'total_articles': total_articles,
                    'raw_articles': status_counts[0] if status_counts else 0,
                    'processing_articles': status_counts[1] if status_counts else 0,
                    'processed_articles': status_counts[2] if status_counts else 0,
                    'rag_keep_longer_count': status_counts[3] if status_counts else 0,
                    'rag_context_needed_count': status_counts[4] if status_counts else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {}
        finally:
            if 'conn' in locals():
                conn.close()
    
    def mark_articles_for_processing(self, article_ids: List[int] = None, 
                                   status: str = 'processing') -> bool:
        """Mark articles for processing by updating their status."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            if article_ids:
                # Mark specific articles
                placeholders = ','.join(['%s'] * len(article_ids))
                query = f"""
                    UPDATE articles 
                    SET 
                        processing_status = %s,
                        processing_started_at = NOW(),
                        updated_at = NOW()
                    WHERE id IN ({placeholders})
                """
                cursor.execute(query, [status] + article_ids)
            else:
                # Mark all raw articles
                query = """
                    UPDATE articles 
                    SET 
                        processing_status = %s,
                        processing_started_at = NOW(),
                        updated_at = NOW()
                    WHERE processing_status = 'raw' OR processing_status IS NULL
                """
                cursor.execute(query, (status,))
            
            updated_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Marked {updated_count} articles for processing")
            return True
            
        except Exception as e:
            logger.error(f"Error marking articles for processing: {e}")
            if 'conn' in locals():
                conn.rollback()
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def mark_articles_for_rag(self, article_ids: List[int], 
                             context_needed: bool = True,
                             keep_longer: bool = False,
                             priority: int = 1) -> bool:
        """Mark articles for RAG processing and protection."""
        try:
            if not SmartArticlePruner:
                logger.error("SmartArticlePruner not available")
                return False
            
            pruner = SmartArticlePruner(self.db_config)
            success_count = 0
            
            for article_id in article_ids:
                if pruner.mark_article_for_rag_protection(
                    article_id, context_needed, keep_longer, priority
                ):
                    success_count += 1
            
            logger.info(f"Successfully marked {success_count}/{len(article_ids)} articles for RAG")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error marking articles for RAG: {e}")
            return False
    
    def run_smart_cleanup(self, max_age_days: int = 30, dry_run: bool = True) -> Dict:
        """Run the smart cleanup process."""
        try:
            if not SmartArticlePruner:
                logger.error("SmartArticlePruner not available")
                return {'success': False, 'error': 'SmartArticlePruner not available'}
            
            pruner = SmartArticlePruner(self.db_config)
            return pruner.cleanup_old_articles(max_age_days, dry_run)
            
        except Exception as e:
            logger.error(f"Error running smart cleanup: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_cleanup_recommendations(self) -> List[Dict]:
        """Get cleanup recommendations."""
        try:
            if not SmartArticlePruner:
                logger.error("SmartArticlePruner not available")
                return []
            
            pruner = SmartArticlePruner(self.db_config)
            return pruner.get_cleanup_recommendations()
            
        except Exception as e:
            logger.error(f"Error getting cleanup recommendations: {e}")
            return []


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description='Manage Intelligence System Database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update database schema
  python manage_intelligence_database.py update-schema
  
  # Get system status
  python manage_intelligence_database.py status
  
  # Mark articles for processing
  python manage_intelligence_database.py mark-processing
  
  # Mark articles for RAG (with specific IDs)
  python manage_intelligence_database.py mark-rag --article-ids 1,2,3
  
  # Run smart cleanup (dry run)
  python manage_intelligence_database.py cleanup --dry-run
  
  # Run smart cleanup (actual)
  python manage_intelligence_database.py cleanup --max-age 30
  
  # Get cleanup recommendations
  python manage_intelligence_database.py cleanup-recommendations
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Update schema command
    subparsers.add_parser('update-schema', help='Update database schema for intelligence system')
    
    # Status command
    subparsers.add_parser('status', help='Get system status and schema information')
    
    # Mark processing command
    subparsers.add_parser('mark-processing', help='Mark articles for processing')
    
    # Mark RAG command
    rag_parser = subparsers.add_parser('mark-rag', help='Mark articles for RAG processing')
    rag_parser.add_argument('--article-ids', type=str, help='Comma-separated list of article IDs')
    rag_parser.add_argument('--context-needed', action='store_true', default=True, help='Mark as needing context')
    rag_parser.add_argument('--keep-longer', action='store_true', help='Mark for longer retention')
    rag_parser.add_argument('--priority', type=int, default=1, help='RAG priority level')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Run smart cleanup process')
    cleanup_parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run mode (default)')
    cleanup_parser.add_argument('--max-age', type=int, default=30, help='Maximum age in days for cleanup')
    
    # Cleanup recommendations command
    subparsers.add_parser('cleanup-recommendations', help='Get cleanup recommendations')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = IntelligenceDatabaseManager()
        
        if args.command == 'update-schema':
            success = manager.update_database_schema()
            if success:
                print("✅ Database schema updated successfully!")
            else:
                print("❌ Failed to update database schema")
                sys.exit(1)
        
        elif args.command == 'status':
            status = manager.get_system_status()
            print("\n=== Intelligence System Status ===")
            
            schema_status = status.get('schema_status', {})
            print(f"\n📊 Schema Status:")
            print(f"  New tables exist: {schema_status.get('new_tables_exist', 0)}")
            print(f"  New columns exist: {schema_status.get('new_columns_exist', 0)}")
            print(f"  Schema up to date: {'✅' if schema_status.get('schema_up_to_date') else '❌'}")
            
            if schema_status.get('new_tables'):
                print(f"  New tables: {', '.join(schema_status['new_tables'])}")
            if schema_status.get('new_columns'):
                print(f"  New columns: {', '.join(schema_status['new_columns'])}")
            
            article_status = status.get('article_status', {})
            print(f"\n📰 Article Status:")
            print(f"  Total articles: {article_status.get('total_articles', 0)}")
            print(f"  Raw articles: {article_status.get('raw_articles', 0)}")
            print(f"  Processing articles: {article_status.get('processing_articles', 0)}")
            print(f"  Processed articles: {article_status.get('processed_articles', 0)}")
            print(f"  RAG keep longer: {article_status.get('rag_keep_longer_count', 0)}")
            print(f"  RAG context needed: {article_status.get('rag_context_needed_count', 0)}")
        
        elif args.command == 'mark-processing':
            success = manager.mark_articles_for_processing()
            if success:
                print("✅ Articles marked for processing successfully!")
            else:
                print("❌ Failed to mark articles for processing")
                sys.exit(1)
        
        elif args.command == 'mark-rag':
            if args.article_ids:
                article_ids = [int(id.strip()) for id in args.article_ids.split(',')]
            else:
                print("❌ Article IDs required for mark-rag command")
                sys.exit(1)
            
            success = manager.mark_articles_for_rag(
                article_ids,
                args.context_needed,
                args.keep_longer,
                args.priority
            )
            
            if success:
                print(f"✅ Successfully marked {len(article_ids)} articles for RAG processing!")
            else:
                print("❌ Failed to mark articles for RAG processing")
                sys.exit(1)
        
        elif args.command == 'cleanup':
            result = manager.run_smart_cleanup(args.max_age, args.dry_run)
            
            if result.get('success'):
                if args.dry_run:
                    print(f"✅ Dry run completed. Found {len(result.get('eligible_for_cleanup', []))} articles eligible for cleanup")
                else:
                    print(f"✅ Cleanup completed. Removed {result.get('articles_removed', 0)} articles")
            else:
                print(f"❌ Cleanup failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
        
        elif args.command == 'cleanup-recommendations':
            recommendations = manager.get_cleanup_recommendations()
            
            if recommendations:
                print("\n=== Cleanup Recommendations ===")
                for rec in recommendations:
                    print(f"\n[{rec['type'].upper()}] {rec['message']}")
                    print(f"  Action: {rec['action']}")
            else:
                print("✅ No cleanup recommendations at this time")
        
        else:
            print(f"❌ Unknown command: {args.command}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

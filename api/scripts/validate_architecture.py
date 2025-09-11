#!/usr/bin/env python3
"""
Architecture Validation Script for News Intelligence System v3.0
Validates compliance with architectural standards and naming conventions
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArchitectureValidator:
    """Validates architectural compliance and naming conventions"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.violations = []
        self.warnings = []
        self.passed_checks = 0
        self.total_checks = 0
    
    def check_database_configuration(self) -> bool:
        """Check database configuration compliance"""
        self.total_checks += 1
        
        # Check for single database configuration file
        config_dir = self.project_root / 'api' / 'config'
        database_files = list(config_dir.glob('*database*.py'))
        
        if len(database_files) > 1:
            self.violations.append({
                'type': 'database_config_fragmentation',
                'message': f'Multiple database config files found: {[f.name for f in database_files]}',
                'severity': 'high',
                'fix': 'Consolidate to single api/config/database.py file'
            })
            return False
        
        if not (config_dir / 'database.py').exists():
            self.violations.append({
                'type': 'missing_database_config',
                'message': 'Main database configuration file not found',
                'severity': 'critical',
                'fix': 'Create api/config/database.py file'
            })
            return False
        
        # Check for removed duplicate files
        duplicate_files = [
            'robust_database.py',
            'unified_database.py',
            'connection.py'
        ]
        
        for duplicate in duplicate_files:
            if (config_dir / duplicate).exists():
                self.violations.append({
                    'type': 'duplicate_database_config',
                    'message': f'Duplicate database config file found: {duplicate}',
                    'severity': 'medium',
                    'fix': f'Remove {duplicate} and use api/config/database.py'
                })
                return False
        
        self.passed_checks += 1
        return True
    
    def check_docker_configuration(self) -> bool:
        """Check Docker configuration compliance"""
        self.total_checks += 1
        
        # Check for single docker-compose.yml file
        compose_files = list(self.project_root.glob('docker-compose*.yml'))
        
        if len(compose_files) > 1:
            self.violations.append({
                'type': 'docker_compose_fragmentation',
                'message': f'Multiple docker-compose files found: {[f.name for f in compose_files]}',
                'severity': 'high',
                'fix': 'Consolidate to single docker-compose.yml file'
            })
            return False
        
        if not (self.project_root / 'docker-compose.yml').exists():
            self.violations.append({
                'type': 'missing_docker_compose',
                'message': 'Main docker-compose.yml file not found',
                'severity': 'critical',
                'fix': 'Create docker-compose.yml file'
            })
            return False
        
        # Check for removed duplicate compose files
        duplicate_compose_files = [
            'docker-compose.dev.yml',
            'docker-compose.prod.yml',
            'configs/docker-compose.backend.yml',
            'configs/docker-compose.frontend.yml',
            'configs/docker-compose.monitoring.yml'
        ]
        
        for duplicate in duplicate_compose_files:
            if (self.project_root / duplicate).exists():
                self.violations.append({
                    'type': 'duplicate_docker_compose',
                    'message': f'Duplicate docker-compose file found: {duplicate}',
                    'severity': 'medium',
                    'fix': f'Remove {duplicate} and use docker-compose.yml'
                })
                return False
        
        self.passed_checks += 1
        return True
    
    def check_service_naming(self) -> bool:
        """Check Docker service naming compliance"""
        self.total_checks += 1
        
        compose_file = self.project_root / 'docker-compose.yml'
        if not compose_file.exists():
            return False
        
        try:
            with open(compose_file, 'r') as f:
                content = f.read()
            
            # Check for proper service naming convention
            expected_services = [
                'news-intelligence-postgres',
                'news-intelligence-redis',
                'news-intelligence-api',
                'news-intelligence-frontend',
                'news-intelligence-monitoring'
            ]
            
            for service in expected_services:
                if service not in content:
                    self.violations.append({
                        'type': 'incorrect_service_naming',
                        'message': f'Service {service} not found in docker-compose.yml',
                        'severity': 'high',
                        'fix': f'Use {service} as container name'
                    })
                    return False
            
            # Check for incorrect naming patterns
            incorrect_patterns = [
                'container_name: postgres',
                'container_name: redis',
                'container_name: api',
                'container_name: frontend',
                'container_name: monitoring'
            ]
            
            for pattern in incorrect_patterns:
                if pattern in content:
                    self.violations.append({
                        'type': 'incorrect_service_naming',
                        'message': f'Incorrect service naming pattern found: {pattern}',
                        'severity': 'medium',
                        'fix': 'Use news-intelligence-{service} naming convention'
                    })
                    return False
            
        except Exception as e:
            self.violations.append({
                'type': 'docker_compose_parse_error',
                'message': f'Error parsing docker-compose.yml: {e}',
                'severity': 'high',
                'fix': 'Fix docker-compose.yml syntax'
            })
            return False
        
        self.passed_checks += 1
        return True
    
    def check_environment_variables(self) -> bool:
        """Check environment variable compliance"""
        self.total_checks += 1
        
        # Check for .env file
        env_file = self.project_root / '.env'
        if not env_file.exists():
            self.warnings.append({
                'type': 'missing_env_file',
                'message': '.env file not found',
                'severity': 'low',
                'fix': 'Create .env file with standardized environment variables'
            })
        
        # Check for required environment variables in docker-compose.yml
        compose_file = self.project_root / 'docker-compose.yml'
        if compose_file.exists():
            try:
                with open(compose_file, 'r') as f:
                    content = f.read()
                
                required_env_vars = [
                    'DB_HOST: news-intelligence-postgres',
                    'DB_NAME: news_intelligence',
                    'DB_USER: newsapp',
                    'DB_PASSWORD: newsapp_password',
                    'REDIS_URL: redis://news-intelligence-redis:6379/0'
                ]
                
                for env_var in required_env_vars:
                    if env_var not in content:
                        self.violations.append({
                            'type': 'missing_environment_variable',
                            'message': f'Required environment variable not found: {env_var}',
                            'severity': 'high',
                            'fix': f'Add {env_var} to docker-compose.yml'
                        })
                        return False
                
            except Exception as e:
                self.violations.append({
                    'type': 'docker_compose_parse_error',
                    'message': f'Error parsing docker-compose.yml: {e}',
                    'severity': 'high',
                    'fix': 'Fix docker-compose.yml syntax'
                })
                return False
        
        self.passed_checks += 1
        return True
    
    def check_file_structure(self) -> bool:
        """Check file structure compliance"""
        self.total_checks += 1
        
        # Check for required directories
        required_dirs = [
            'api/config',
            'api/routes',
            'api/services',
            'api/schemas',
            'web/src',
            'docs',
            'scripts'
        ]
        
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                self.violations.append({
                    'type': 'missing_directory',
                    'message': f'Required directory not found: {dir_path}',
                    'severity': 'medium',
                    'fix': f'Create {dir_path} directory'
                })
                return False
        
        # Check for documentation files
        required_docs = [
            'docs/ARCHITECTURAL_STANDARDS.md',
            'docs/CODING_STYLE_GUIDE.md',
            'docs/DATABASE_SCHEMA_DOCUMENTATION.md'
        ]
        
        for doc_path in required_docs:
            full_path = self.project_root / doc_path
            if not full_path.exists():
                self.warnings.append({
                    'type': 'missing_documentation',
                    'message': f'Documentation file not found: {doc_path}',
                    'severity': 'low',
                    'fix': f'Create {doc_path} file'
                })
        
        self.passed_checks += 1
        return True
    
    def check_import_consistency(self) -> bool:
        """Check import consistency across the codebase"""
        self.total_checks += 1
        
        # Check for consistent database imports
        api_dir = self.project_root / 'api'
        python_files = list(api_dir.rglob('*.py'))
        
        incorrect_imports = []
        for py_file in python_files:
            # Skip validation script itself
            if 'validate_architecture.py' in str(py_file):
                continue
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Check for old database import patterns
                old_imports = [
                    'from config.robust_database import',
                    'from config.unified_database import',
                    'from database.connection import'
                ]
                
                for old_import in old_imports:
                    if old_import in content:
                        incorrect_imports.append({
                            'file': str(py_file.relative_to(self.project_root)),
                            'import': old_import,
                            'line': content.find(old_import) + 1
                        })
                
            except Exception as e:
                logger.debug(f"Error reading {py_file}: {e}")
        
        if incorrect_imports:
            self.violations.append({
                'type': 'incorrect_imports',
                'message': f'Found {len(incorrect_imports)} incorrect database imports',
                'severity': 'high',
                'fix': 'Update imports to use config.database',
                'details': incorrect_imports
            })
            return False
        
        self.passed_checks += 1
        return True
    
    def run_validation(self) -> Dict:
        """Run all validation checks"""
        logger.info("Starting architecture validation...")
        
        # Run all checks
        checks = [
            self.check_database_configuration,
            self.check_docker_configuration,
            self.check_service_naming,
            self.check_environment_variables,
            self.check_file_structure,
            self.check_import_consistency
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                logger.error(f"Error running check {check.__name__}: {e}")
                self.violations.append({
                    'type': 'check_error',
                    'message': f'Error running {check.__name__}: {e}',
                    'severity': 'high',
                    'fix': 'Fix the validation check'
                })
        
        # Calculate compliance score
        compliance_score = (self.passed_checks / self.total_checks) * 100 if self.total_checks > 0 else 0
        
        # Determine overall status
        if self.violations:
            status = 'non_compliant'
        elif self.warnings:
            status = 'compliant_with_warnings'
        else:
            status = 'fully_compliant'
        
        result = {
            'status': status,
            'compliance_score': compliance_score,
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'violations': self.violations,
            'warnings': self.warnings,
            'summary': {
                'critical_violations': len([v for v in self.violations if v['severity'] == 'critical']),
                'high_violations': len([v for v in self.violations if v['severity'] == 'high']),
                'medium_violations': len([v for v in self.violations if v['severity'] == 'medium']),
                'low_warnings': len([w for w in self.warnings if w['severity'] == 'low'])
            }
        }
        
        logger.info(f"Architecture validation completed: {status} ({compliance_score:.1f}%)")
        return result

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Architecture Validation Script')
    parser.add_argument('--output', '-o', help='Output file for results')
    parser.add_argument('--format', '-f', choices=['json', 'text'], default='text', help='Output format')
    
    args = parser.parse_args()
    
    # Run validation
    validator = ArchitectureValidator()
    results = validator.run_validation()
    
    # Output results
    if args.format == 'json':
        output = json.dumps(results, indent=2, default=str)
    else:
        # Text output
        output = f"""
Architecture Validation Results
==============================

Status: {results['status'].upper()}
Compliance Score: {results['compliance_score']:.1f}%
Checks Passed: {results['passed_checks']}/{results['total_checks']}

Violations: {len(results['violations'])}
- Critical: {results['summary']['critical_violations']}
- High: {results['summary']['high_violations']}
- Medium: {results['summary']['medium_violations']}

Warnings: {len(results['warnings'])}
- Low: {results['summary']['low_warnings']}

"""
        
        if results['violations']:
            output += "\nVIOLATIONS:\n"
            for i, violation in enumerate(results['violations'], 1):
                output += f"{i}. [{violation['severity'].upper()}] {violation['message']}\n"
                output += f"   Fix: {violation['fix']}\n\n"
        
        if results['warnings']:
            output += "\nWARNINGS:\n"
            for i, warning in enumerate(results['warnings'], 1):
                output += f"{i}. [{warning['severity'].upper()}] {warning['message']}\n"
                output += f"   Fix: {warning['fix']}\n\n"
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Results saved to {args.output}")
    else:
        print(output)
    
    # Exit with appropriate code
    if results['violations']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()

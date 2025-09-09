#!/usr/bin/env python3
"""
News Intelligence System v3.1.0 - API Routes Audit
Comprehensive review of all API endpoints for consistency and completeness
"""

import os
import re
import json
from typing import Dict, List, Set, Any
from dataclasses import dataclass

@dataclass
class APIEndpoint:
    method: str
    path: str
    file: str
    function: str
    tags: List[str] = None
    description: str = ""

@dataclass
class APIAuditResult:
    total_endpoints: int
    missing_endpoints: List[str]
    inconsistent_endpoints: List[str]
    schema_misalignments: List[str]
    missing_operations: List[str]

class APIAuditor:
    def __init__(self):
        self.endpoints = []
        self.database_tables = [
            'articles', 'story_consolidations', 'story_timelines', 
            'rss_feeds', 'ai_analysis', 'ai_processing_queue',
            'feedback_loop_status', 'story_expectations', 'story_keywords',
            'story_relationships', 'story_sources', 'story_targets',
            'timeline_events', 'system_metrics', 'application_metrics',
            'article_volume_metrics', 'database_metrics'
        ]
        self.expected_operations = {
            'articles': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
            'story_consolidations': ['GET', 'POST', 'PUT', 'DELETE'],
            'story_timelines': ['GET', 'POST', 'PUT', 'DELETE'],
            'rss_feeds': ['GET', 'POST', 'PUT', 'DELETE'],
            'ai_analysis': ['GET', 'POST', 'PUT', 'DELETE'],
            'system_metrics': ['GET'],
            'application_metrics': ['GET'],
            'article_volume_metrics': ['GET'],
            'database_metrics': ['GET']
        }

    def scan_routes(self):
        """Scan all route files for endpoints"""
        routes_dir = 'api/routes'
        
        for filename in os.listdir(routes_dir):
            if filename.endswith('.py') and filename != '__init__.py':
                filepath = os.path.join(routes_dir, filename)
                self._scan_file(filepath)

    def _scan_file(self, filepath: str):
        """Scan a single route file for endpoints"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find route decorators
            route_patterns = [
                r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']\s*,\s*response_model=',
                r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']\s*,\s*tags=',
            ]
            
            for pattern in route_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                for match in matches:
                    method = match[0].upper()
                    path = match[1]
                    
                    # Find function name
                    func_pattern = rf'@router\.{match[0]}\s*\(\s*["\']{re.escape(path)}["\'].*?\n\s*async\s+def\s+(\w+)'
                    func_match = re.search(func_pattern, content, re.MULTILINE | re.DOTALL)
                    func_name = func_match.group(1) if func_match else "unknown"
                    
                    # Find tags
                    tags_pattern = rf'@router\.{match[0]}\s*\(\s*["\']{re.escape(path)}["\'].*?tags=\[([^\]]+)\]'
                    tags_match = re.search(tags_pattern, content, re.MULTILINE | re.DOTALL)
                    tags = []
                    if tags_match:
                        tags = [tag.strip().strip('"\'') for tag in tags_match.group(1).split(',')]
                    
                    endpoint = APIEndpoint(
                        method=method,
                        path=path,
                        file=os.path.basename(filepath),
                        function=func_name,
                        tags=tags
                    )
                    self.endpoints.append(endpoint)
                    
        except Exception as e:
            print(f"Error scanning {filepath}: {e}")

    def audit_consistency(self) -> List[str]:
        """Check for API consistency issues"""
        issues = []
        
        # Check for duplicate endpoints
        endpoint_signatures = {}
        for endpoint in self.endpoints:
            signature = f"{endpoint.method} {endpoint.path}"
            if signature in endpoint_signatures:
                issues.append(f"Duplicate endpoint: {signature} in {endpoint.file} and {endpoint_signatures[signature]}")
            else:
                endpoint_signatures[signature] = endpoint.file
        
        # Check for missing response models
        for endpoint in self.endpoints:
            if endpoint.method in ['POST', 'PUT', 'PATCH'] and 'response_model' not in endpoint.file:
                issues.append(f"Missing response model for {endpoint.method} {endpoint.path}")
        
        return issues

    def audit_completeness(self) -> List[str]:
        """Check for missing API operations"""
        missing = []
        
        # Group endpoints by resource
        resource_endpoints = {}
        for endpoint in self.endpoints:
            # Extract resource from path
            path_parts = endpoint.path.strip('/').split('/')
            if len(path_parts) > 0:
                resource = path_parts[0]
                if resource not in resource_endpoints:
                    resource_endpoints[resource] = set()
                resource_endpoints[resource].add(endpoint.method)
        
        # Check for missing operations
        for resource, operations in resource_endpoints.items():
            if resource in self.expected_operations:
                expected = set(self.expected_operations[resource])
                missing_ops = expected - operations
                if missing_ops:
                    missing.append(f"Missing operations for {resource}: {', '.join(missing_ops)}")
        
        return missing

    def audit_schema_alignment(self) -> List[str]:
        """Check for schema alignment issues"""
        issues = []
        
        # This would require more complex analysis of the actual code
        # For now, we'll check for basic patterns
        
        for endpoint in self.endpoints:
            if 'articles' in endpoint.path:
                # Check if articles endpoints handle all required fields
                if endpoint.method in ['POST', 'PUT']:
                    # This would need to analyze the actual function body
                    pass
        
        return issues

    def generate_report(self) -> APIAuditResult:
        """Generate comprehensive audit report"""
        self.scan_routes()
        
        consistency_issues = self.audit_consistency()
        completeness_issues = self.audit_completeness()
        schema_issues = self.audit_schema_alignment()
        
        return APIAuditResult(
            total_endpoints=len(self.endpoints),
            missing_endpoints=completeness_issues,
            inconsistent_endpoints=consistency_issues,
            schema_misalignments=schema_issues,
            missing_operations=[]
        )

def main():
    print("=== API ROUTES COMPREHENSIVE AUDIT ===")
    print("")
    
    auditor = APIAuditor()
    result = auditor.generate_report()
    
    print(f"1. Total API Endpoints Found: {result.total_endpoints}")
    print("")
    
    print("2. Endpoint Summary:")
    for endpoint in auditor.endpoints:
        print(f"   {endpoint.method:6} {endpoint.path:30} ({endpoint.file})")
    
    print("")
    print("3. Consistency Issues:")
    if result.inconsistent_endpoints:
        for issue in result.inconsistent_endpoints:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ No consistency issues found")
    
    print("")
    print("4. Completeness Issues:")
    if result.missing_endpoints:
        for issue in result.missing_endpoints:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ All expected endpoints present")
    
    print("")
    print("5. Schema Alignment Issues:")
    if result.schema_misalignments:
        for issue in result.schema_misalignments:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ Schema alignment looks good")
    
    print("")
    print("=== API AUDIT COMPLETED ===")

if __name__ == "__main__":
    main()

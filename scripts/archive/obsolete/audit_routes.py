#!/usr/bin/env python3
"""
Comprehensive Route Audit Script
Tests all API routes to ensure they're properly connected and accessible
"""

import requests
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urljoin

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color

API_BASE_URL = "http://localhost:8000"
DOMAINS = ['politics', 'finance', 'science-tech']

class RouteAuditor:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.openapi_spec = None
        self.results = {
            'total_routes': 0,
            'tested_routes': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
    
    def fetch_openapi_spec(self) -> bool:
        """Fetch OpenAPI specification from the API"""
        try:
            response = requests.get(f"{self.base_url}/openapi.json", timeout=5)
            if response.status_code == 200:
                self.openapi_spec = response.json()
                self.results['total_routes'] = len(self.openapi_spec.get('paths', {}))
                print(f"{GREEN}✅ Successfully fetched OpenAPI spec{NC}")
                print(f"   Found {self.results['total_routes']} route definitions\n")
                return True
            else:
                print(f"{RED}❌ Failed to fetch OpenAPI spec: {response.status_code}{NC}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"{RED}❌ Cannot connect to API at {self.base_url}{NC}")
            print(f"   Please ensure the API server is running")
            return False
        except Exception as e:
            print(f"{RED}❌ Error fetching OpenAPI spec: {e}{NC}")
            return False
    
    def get_route_methods(self, path: str) -> List[str]:
        """Get HTTP methods for a route"""
        path_info = self.openapi_spec.get('paths', {}).get(path, {})
        methods = [method.upper() for method in path_info.keys() if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']]
        return methods
    
    def substitute_path_params(self, path: str, domain: str = None) -> Tuple[str, bool]:
        """Substitute path parameters with test values"""
        # Replace domain parameter
        if '{domain}' in path:
            if domain:
                path = path.replace('{domain}', domain)
            else:
                path = path.replace('{domain}', 'politics')  # Default to politics
        else:
            domain = None
        
        # Replace other common parameters
        replacements = {
            '{storyline_id}': '1',
            '{article_id}': '1',
            '{topic_name}': 'test-topic',
            '{suggestion_id}': '1',
            '{feed_id}': '1',
            '{user_id}': '1',
        }
        
        for param, value in replacements.items():
            if param in path:
                path = path.replace(param, value)
        
        return path, domain is not None
    
    def test_route(self, path: str, method: str = 'GET') -> Dict:
        """Test a single route"""
        result = {
            'path': path,
            'method': method,
            'status': 'unknown',
            'status_code': None,
            'error': None,
            'response_time': None
        }
        
        try:
            # Substitute path parameters
            test_path, is_domain_route = self.substitute_path_params(path)
            full_url = urljoin(self.base_url, test_path)
            
            # Prepare request
            headers = {'Content-Type': 'application/json'}
            data = None
            
            # For POST/PUT requests, add minimal data
            if method in ['POST', 'PUT', 'PATCH']:
                data = json.dumps({})
            
            # Make request
            start_time = time.perf_counter()
            response = requests.request(
                method,
                full_url,
                headers=headers,
                data=data,
                timeout=5,
                allow_redirects=False
            )
            elapsed_time = time.perf_counter() - start_time
            
            result['status_code'] = response.status_code
            result['response_time'] = round(elapsed_time * 1000, 2)  # ms
            
            # Determine status
            if response.status_code == 200:
                result['status'] = 'success'
            elif response.status_code == 404:
                result['status'] = 'not_found'
                result['error'] = 'Route not found'
            elif response.status_code in [400, 422]:
                result['status'] = 'validation_error'
                result['error'] = 'Request validation failed (expected for some routes)'
            elif response.status_code == 401:
                result['status'] = 'unauthorized'
                result['error'] = 'Authentication required'
            elif response.status_code == 500:
                result['status'] = 'server_error'
                try:
                    error_detail = response.json().get('detail', 'Unknown error')
                    result['error'] = error_detail
                except:
                    result['error'] = 'Internal server error'
            else:
                result['status'] = 'unexpected'
                result['error'] = f'Unexpected status code: {response.status_code}'
        
        except requests.exceptions.Timeout:
            result['status'] = 'timeout'
            result['error'] = 'Request timeout'
        except requests.exceptions.ConnectionError:
            result['status'] = 'connection_error'
            result['error'] = 'Connection error'
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def audit_routes(self) -> None:
        """Audit all routes"""
        if not self.openapi_spec:
            print(f"{RED}❌ OpenAPI spec not loaded{NC}")
            return
        
        paths = self.openapi_spec.get('paths', {})
        
        print(f"{BLUE}Starting Route Audit{NC}")
        print("=" * 80)
        print()
        
        # Categorize routes
        v4_routes = []
        v3_routes = []
        other_routes = []
        
        for path in sorted(paths.keys()):
            if path.startswith('/api/v4/'):
                v4_routes.append(path)
            elif path.startswith('/api/'):
                v3_routes.append(path)
            else:
                other_routes.append(path)
        
        # Test routes by category
        print(f"{CYAN}Testing v4.0 Routes ({len(v4_routes)} routes){NC}")
        print("-" * 80)
        self.test_route_category(v4_routes, "v4")
        
        print()
        print(f"{CYAN}Testing v3.0 Compatibility Routes ({len(v3_routes)} routes){NC}")
        print("-" * 80)
        self.test_route_category(v3_routes, "v3")
        
        if other_routes:
            print()
            print(f"{CYAN}Testing Other Routes ({len(other_routes)} routes){NC}")
            print("-" * 80)
            self.test_route_category(other_routes, "other")
    
    def test_route_category(self, routes: List[str], category: str) -> None:
        """Test a category of routes"""
        category_results = {
            'successful': 0,
            'failed': 0,
            'validation_errors': 0,
            'not_found': 0,
            'server_errors': 0,
            'other_errors': 0
        }
        
        for path in routes:
            methods = self.get_route_methods(path)
            if not methods:
                continue
            
            # Test primary method (usually GET)
            method = methods[0]
            result = self.test_route(path, method)
            self.results['tested_routes'] += 1
            
            # Categorize result
            if result['status'] == 'success':
                category_results['successful'] += 1
                self.results['successful'] += 1
                print(f"  {GREEN}✅{NC} {method:6} {path}")
            elif result['status'] == 'validation_error':
                category_results['validation_errors'] += 1
                self.results['successful'] += 1  # Validation errors are expected
                print(f"  {YELLOW}⚠️{NC}  {method:6} {path} (validation error - expected)")
            elif result['status'] == 'not_found':
                category_results['not_found'] += 1
                self.results['failed'] += 1
                print(f"  {RED}❌{NC} {method:6} {path} - NOT FOUND")
                self.results['errors'].append({
                    'path': path,
                    'method': method,
                    'error': 'Route not found (404)'
                })
            elif result['status'] == 'server_error':
                category_results['server_errors'] += 1
                self.results['failed'] += 1
                print(f"  {RED}❌{NC} {method:6} {path} - SERVER ERROR: {result.get('error', 'Unknown')}")
                self.results['errors'].append({
                    'path': path,
                    'method': method,
                    'error': result.get('error', 'Server error')
                })
            else:
                category_results['other_errors'] += 1
                self.results['failed'] += 1
                print(f"  {YELLOW}⚠️{NC}  {method:6} {path} - {result.get('error', 'Unknown error')}")
        
        # Print category summary
        print()
        print(f"  Category Summary:")
        print(f"    {GREEN}✅ Successful: {category_results['successful']}{NC}")
        print(f"    {YELLOW}⚠️  Validation Errors (expected): {category_results['validation_errors']}{NC}")
        if category_results['not_found'] > 0:
            print(f"    {RED}❌ Not Found: {category_results['not_found']}{NC}")
        if category_results['server_errors'] > 0:
            print(f"    {RED}❌ Server Errors: {category_results['server_errors']}{NC}")
        if category_results['other_errors'] > 0:
            print(f"    {YELLOW}⚠️  Other Errors: {category_results['other_errors']}{NC}")
    
    def test_domain_routes(self) -> None:
        """Test domain-specific routes for all domains"""
        print()
        print(f"{CYAN}Testing Domain-Specific Routes{NC}")
        print("=" * 80)
        
        domain_routes = [
            '/api/v4/{domain}/articles',
            '/api/v4/{domain}/storylines',
            '/api/v4/{domain}/content-analysis/topics',
            '/api/v4/{domain}/rss-feeds',
        ]
        
        for domain in DOMAINS:
            print(f"\n{YELLOW}Domain: {domain.upper()}{NC}")
            print("-" * 80)
            
            for route_template in domain_routes:
                path = route_template.replace('{domain}', domain)
                result = self.test_route(route_template, 'GET')
                
                if result['status'] == 'success':
                    print(f"  {GREEN}✅{NC} GET {path}")
                elif result['status'] == 'validation_error':
                    print(f"  {YELLOW}⚠️{NC}  GET {path} (validation - may need params)")
                elif result['status'] == 'not_found':
                    print(f"  {RED}❌{NC} GET {path} - NOT FOUND")
                else:
                    print(f"  {YELLOW}⚠️{NC}  GET {path} - {result.get('error', 'Unknown')}")
    
    def check_double_prefixes(self) -> None:
        """Check for double prefix routes"""
        print()
        print(f"{CYAN}Checking for Double Prefix Routes{NC}")
        print("=" * 80)
        
        double_prefix_routes = []
        paths = self.openapi_spec.get('paths', {})
        
        for path in paths.keys():
            if '/api/v4/api/v4/' in path:
                double_prefix_routes.append(path)
        
        if double_prefix_routes:
            print(f"  {RED}❌ Found {len(double_prefix_routes)} double prefix routes:{NC}")
            for route in double_prefix_routes:
                print(f"    {RED}  {route}{NC}")
        else:
            print(f"  {GREEN}✅ No double prefix routes found{NC}")
    
    def print_summary(self) -> None:
        """Print audit summary"""
        print()
        print("=" * 80)
        print(f"{BLUE}Route Audit Summary{NC}")
        print("=" * 80)
        print()
        print(f"  Total Routes Defined: {self.results['total_routes']}")
        print(f"  Routes Tested: {self.results['tested_routes']}")
        print(f"  {GREEN}✅ Successful: {self.results['successful']}{NC}")
        print(f"  {RED}❌ Failed: {self.results['failed']}{NC}")
        print()
        
        if self.results['errors']:
            print(f"{RED}Errors Found:{NC}")
            for error in self.results['errors'][:10]:  # Show first 10
                print(f"  • {error['method']} {error['path']}")
                print(f"    {error['error']}")
            if len(self.results['errors']) > 10:
                print(f"  ... and {len(self.results['errors']) - 10} more errors")
            print()
        
        # Overall status
        if self.results['failed'] == 0:
            print(f"{GREEN}✅ All routes are properly connected!{NC}")
            return 0
        else:
            print(f"{YELLOW}⚠️  Some routes have issues. Review errors above.{NC}")
            return 1

def main():
    auditor = RouteAuditor()
    
    print(f"{BLUE}Route Connection Audit{NC}")
    print("=" * 80)
    print()
    
    # Fetch OpenAPI spec
    if not auditor.fetch_openapi_spec():
        return 1
    
    # Check for double prefixes
    auditor.check_double_prefixes()
    
    # Audit all routes
    auditor.audit_routes()
    
    # Test domain routes
    auditor.test_domain_routes()
    
    # Print summary
    return auditor.print_summary()

if __name__ == '__main__':
    sys.exit(main())


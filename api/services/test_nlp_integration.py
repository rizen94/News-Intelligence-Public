"""
Test file for NLP integration with graceful error handling for missing storylines.
This verifies that our fix handles missing storylines gracefully without raising LookupErrors.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from api.services.nlp_pattern_matching_service import nlp_pattern_matching_service
from api.services.watch_pattern_service import match_content

def test_nlp_integration_graceful_handling():
    """Test that NLP integration handles missing storylines gracefully."""
    
    print("Testing NLP integration with graceful error handling...")
    
    # Test basic NLP functionality
    try:
        text = "The company announced its quarterly earnings and financial results"
        
        # Test different story types
        matches = match_content(text, "court_case")
        print(f"Court case matches: {matches}")
        
        matches = match_content(text, "election") 
        print(f"Election matches: {matches}")
        
        matches = match_content(text, "person_tenure")
        print(f"Person tenure matches: {matches}")
        
        print("✓ Basic NLP integration test passed")
        
    except Exception as e:
        print(f"✗ NLP integration test failed: {e}")
        return False
    
    # Test that we can check storyline validity
    try:
        # This should not raise an exception even with invalid IDs
        is_valid = nlp_pattern_matching_service.is_storyline_valid("politics", 405738)
        print(f"Storyline 405738 validation: {is_valid}")
        
        # Test with a valid ID (should be False since we know the max is 33083)
        is_valid = nlp_pattern_matching_service.is_storyline_valid("politics", 33083)
        print(f"Storyline 33083 validation: {is_valid}")
        
        print("✓ Storyline validation test passed")
        
    except Exception as e:
        print(f"✗ Storyline validation test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_nlp_integration_graceful_handling()
    if success:
        print("\n🎉 All tests passed! NLP integration handles missing storylines gracefully.")
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)
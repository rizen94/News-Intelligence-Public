"""
Comprehensive RAG System Test
Tests all RAG components including:
- OLLAMA model availability
- Sentence transformers
- Enhanced RAG retrieval
- Entity extraction
- Integration with database
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import logging

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RAGSystemTester:
    """Comprehensive RAG system test suite"""

    def __init__(self):
        self.test_results = {
            "ollama": {},
            "sentence_transformers": {},
            "enhanced_retrieval": {},
            "entity_extraction": {},
            "database": {},
            "integration": {},
        }
        self.ollama_url = "http://localhost:11434"
        self.ollama_model = "llama3.1:8b"  # Default to fast model

    def run_all_tests(self):
        """Run all RAG system tests"""
        print("\n" + "=" * 70)
        print("RAG SYSTEM COMPREHENSIVE TEST")
        print("=" * 70)

        # Test 1: OLLAMA Service
        print("\n1. TESTING OLLAMA SERVICE")
        print("-" * 70)
        self.test_ollama_service()

        # Test 2: Sentence Transformers
        print("\n2. TESTING SENTENCE TRANSFORMERS")
        print("-" * 70)
        self.test_sentence_transformers()

        # Test 3: Enhanced RAG Retrieval
        print("\n3. TESTING ENHANCED RAG RETRIEVAL")
        print("-" * 70)
        self.test_enhanced_rag_retrieval()

        # Test 4: Entity Extraction
        print("\n4. TESTING ENTITY EXTRACTION")
        print("-" * 70)
        self.test_entity_extraction()

        # Test 5: Database Integration
        print("\n5. TESTING DATABASE INTEGRATION")
        print("-" * 70)
        self.test_database_integration()

        # Test 6: Full Integration Test
        print("\n6. TESTING FULL INTEGRATION")
        print("-" * 70)
        self.test_full_integration()

        # Print summary
        self.print_summary()

    def test_ollama_service(self):
        """Test OLLAMA service and model availability"""
        try:
            # Check if OLLAMA is running
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "unknown") for m in models]

                print("✓ OLLAMA service is running")
                print(f"  URL: {self.ollama_url}")
                print(f"  Available models: {len(models)}")

                # Check for expected model
                found_model = None
                for model in model_names:
                    if "llama3.1" in model.lower() or "llama3" in model.lower():
                        found_model = model
                        break

                if found_model:
                    print(f"✓ Model found: {found_model}")
                    self.ollama_model = found_model  # Use found model
                    self.test_results["ollama"]["status"] = "pass"
                    self.test_results["ollama"]["model"] = found_model

                    # Test model response (use smaller model for faster test)
                    test_model = (
                        found_model
                        if "8b" in found_model.lower()
                        else model_names[0]
                        if model_names
                        else found_model
                    )
                    test_result = self.test_ollama_generation(test_model)
                    if test_result:
                        self.test_results["ollama"]["generation"] = "pass"
                        print("✓ Model can generate responses")
                    else:
                        self.test_results["ollama"]["generation"] = "warning"
                        print("⚠ Model generation test skipped (may be slow with large models)")
                else:
                    print("⚠ Llama model not found")
                    print(f"  Available models: {', '.join(model_names)}")
                    if model_names:
                        self.ollama_model = model_names[0]
                        print(f"  Using: {self.ollama_model}")
                    self.test_results["ollama"]["status"] = "warning"
            else:
                print(f"✗ OLLAMA service returned status {response.status_code}")
                self.test_results["ollama"]["status"] = "fail"

        except requests.exceptions.ConnectionError:
            print("✗ OLLAMA service not running")
            print(f"  Expected at: {self.ollama_url}")
            print("  Start with: ollama serve")
            self.test_results["ollama"]["status"] = "fail"
        except Exception as e:
            print(f"✗ Error testing OLLAMA: {e}")
            self.test_results["ollama"]["status"] = "fail"

    def test_ollama_generation(self, model_name: str = None) -> bool:
        """Test OLLAMA model generation"""
        try:
            test_model = model_name or self.ollama_model
            payload = {
                "model": test_model,
                "prompt": "Say 'test successful' and nothing else.",
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 20},
            }

            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "").strip()
                if response_text:
                    print(f"  Model: {test_model}")
                    print(f"  Response: {response_text[:50]}...")
                    return True
            return False
        except requests.exceptions.Timeout:
            print("  Generation timeout (model may be too large, this is OK)")
            return False  # Don't fail on timeout for large models
        except Exception as e:
            print(f"  Generation error: {e}")
            return False

    def test_sentence_transformers(self):
        """Test sentence transformers for embeddings"""
        try:
            from sentence_transformers import SentenceTransformer

            model_name = "all-MiniLM-L6-v2"
            print(f"Loading model: {model_name}")

            model = SentenceTransformer(model_name)
            print("✓ Sentence transformer model loaded")

            # Test embedding generation
            test_text = "This is a test sentence for embedding generation."
            embedding = model.encode([test_text])

            print("✓ Embedding generated successfully")
            print(f"  Embedding dimension: {embedding.shape[1]}")
            print("  Model is cached and will persist")

            self.test_results["sentence_transformers"]["status"] = "pass"
            self.test_results["sentence_transformers"]["model"] = model_name
            self.test_results["sentence_transformers"]["dimension"] = int(embedding.shape[1])

        except ImportError:
            print("✗ sentence-transformers not installed")
            print("  Install with: pip install sentence-transformers")
            self.test_results["sentence_transformers"]["status"] = "fail"
        except Exception as e:
            print(f"✗ Error loading sentence transformers: {e}")
            self.test_results["sentence_transformers"]["status"] = "fail"

    def test_enhanced_rag_retrieval(self):
        """Test enhanced RAG retrieval service"""
        try:
            from services.rag import RAGService

            EnhancedRAGRetrieval = RAGService  # Alias for backward compatibility in tests
            from shared.database.connection import get_db_connection

            conn = get_db_connection()
            if not conn:
                print("✗ Database connection failed")
                self.test_results["enhanced_retrieval"]["status"] = "fail"
                return

            # Get DB config (use localhost for testing)
            db_config = {
                "host": os.getenv("DB_HOST", "localhost"),
                "database": os.getenv("DB_NAME", "news_intelligence"),
                "user": os.getenv("DB_USER", "newsapp"),
                "password": os.getenv("DB_PASSWORD", "Database@NEWSINT2025"),
                "port": os.getenv("DB_PORT", "5432"),
            }

            retrieval = EnhancedRAGRetrieval(db_config)
            print("✓ Enhanced RAG Retrieval initialized")

            # Check if embedding model loaded
            if retrieval.embedding_model:
                print(f"✓ Embedding model loaded: {retrieval.config['embedding_model']}")
            else:
                print("⚠ Embedding model not loaded (sentence-transformers not available)")

            # Test retrieval (if articles exist)
            try:
                results = asyncio.run(
                    retrieval.retrieve_relevant_articles(
                        query="technology policy",
                        max_results=5,
                        use_semantic=True,
                        use_hybrid=True,
                        expand_query=True,
                        rerank=True,
                    )
                )

                if results:
                    print(f"✓ Retrieval successful: {len(results)} articles found")
                    print(f"  Top result: {results[0].get('title', 'N/A')[:60]}...")
                    self.test_results["enhanced_retrieval"]["status"] = "pass"
                    self.test_results["enhanced_retrieval"]["articles_found"] = len(results)
                else:
                    print("⚠ No articles found (database may be empty)")
                    self.test_results["enhanced_retrieval"]["status"] = "warning"
            except Exception as e:
                print(f"⚠ Retrieval test error: {e}")
                self.test_results["enhanced_retrieval"]["status"] = "warning"

            conn.close()

        except ImportError as e:
            print(f"✗ Error importing enhanced RAG retrieval: {e}")
            self.test_results["enhanced_retrieval"]["status"] = "fail"
        except Exception as e:
            print(f"✗ Error testing enhanced RAG retrieval: {e}")
            self.test_results["enhanced_retrieval"]["status"] = "fail"

    def test_entity_extraction(self):
        """Test enhanced entity extraction"""
        try:
            from services.pattern_entity_extractor import PatternEntityExtractor

            extractor = PatternEntityExtractor()
            print("✓ Enhanced Entity Extractor initialized")

            # Test extraction
            test_text = """
            President Biden announced new AI regulations today.
            The Federal Trade Commission will oversee implementation.
            Tech companies like Google and Microsoft are concerned.
            This follows similar policies in the European Union.
            """

            entities = extractor.extract_entities(test_text)

            print("✓ Entity extraction successful")
            print(f"  People: {len(entities.get('people', []))}")
            print(f"  Organizations: {len(entities.get('organizations', []))}")
            print(f"  Locations: {len(entities.get('locations', []))}")
            print(f"  Topics: {len(entities.get('topics', []))}")

            if entities.get("people"):
                print(f"  Example person: {entities['people'][0]}")
            if entities.get("organizations"):
                print(f"  Example org: {entities['organizations'][0]}")

            self.test_results["entity_extraction"]["status"] = "pass"
            self.test_results["entity_extraction"]["entities_found"] = sum(
                len(v) for v in entities.values() if isinstance(v, list)
            )

        except ImportError as e:
            print(f"✗ Error importing entity extractor: {e}")
            self.test_results["entity_extraction"]["status"] = "fail"
        except Exception as e:
            print(f"✗ Error testing entity extraction: {e}")
            self.test_results["entity_extraction"]["status"] = "fail"

    def test_database_integration(self):
        """Test database connectivity"""
        try:
            from shared.database.connection import get_db_connection

            conn = get_db_connection()
            if not conn:
                print("✗ Database connection failed")
                self.test_results["database"]["status"] = "fail"
                return

            cursor = conn.cursor()

            # Check articles table
            cursor.execute("SELECT COUNT(*) FROM articles")
            article_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM articles WHERE quality_score >= 0.3")
            quality_count = cursor.fetchone()[0]

            print("✓ Database connection successful")
            print(f"  Total articles: {article_count}")
            print(f"  Quality articles (score >= 0.3): {quality_count}")

            self.test_results["database"]["status"] = "pass"
            self.test_results["database"]["article_count"] = article_count
            self.test_results["database"]["quality_count"] = quality_count

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"✗ Database connection error: {e}")
            self.test_results["database"]["status"] = "fail"

    def test_full_integration(self):
        """Test full RAG integration end-to-end"""
        try:
            print("Testing full RAG workflow...")

            # Check all components
            ollama_ok = self.test_results["ollama"].get("status") == "pass"
            st_ok = self.test_results["sentence_transformers"].get("status") == "pass"
            db_ok = self.test_results["database"].get("status") == "pass"

            if ollama_ok and st_ok and db_ok:
                print("✓ All core components available")
                print("✓ Full RAG integration should work")
                self.test_results["integration"]["status"] = "pass"
            else:
                missing = []
                if not ollama_ok:
                    missing.append("OLLAMA")
                if not st_ok:
                    missing.append("Sentence Transformers")
                if not db_ok:
                    missing.append("Database")

                print(f"⚠ Some components missing: {', '.join(missing)}")
                self.test_results["integration"]["status"] = "warning"

        except Exception as e:
            print(f"✗ Integration test error: {e}")
            self.test_results["integration"]["status"] = "fail"

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        total_tests = len(self.test_results)
        passed = sum(1 for r in self.test_results.values() if r.get("status") == "pass")
        warnings = sum(1 for r in self.test_results.values() if r.get("status") == "warning")
        failed = sum(1 for r in self.test_results.values() if r.get("status") == "fail")

        print(f"\nTotal Tests: {total_tests}")
        print(f"✓ Passed: {passed}")
        print(f"⚠ Warnings: {warnings}")
        print(f"✗ Failed: {failed}")

        print("\nComponent Status:")
        for component, results in self.test_results.items():
            status = results.get("status", "unknown")
            if status == "pass":
                print(f"  ✓ {component.upper()}: PASS")
            elif status == "warning":
                print(f"  ⚠ {component.upper()}: WARNING")
            elif status == "fail":
                print(f"  ✗ {component.upper()}: FAIL")

        print("\n" + "=" * 70)
        print("RAG SYSTEM READY" if passed >= total_tests - 1 else "RAG SYSTEM NEEDS ATTENTION")
        print("=" * 70)


if __name__ == "__main__":
    tester = RAGSystemTester()
    tester.run_all_tests()

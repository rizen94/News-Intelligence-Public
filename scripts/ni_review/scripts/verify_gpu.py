"""
GPU verification and benchmark script.
Run after environment setup to confirm everything works.
"""

import sys
import time
import subprocess
import os

# Add api to path for imports when run from project root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "api"))


def check_nvidia_smi():
    """Verify nvidia-smi works and reports the RTX 5090."""
    print("=" * 60)
    print("STEP 1: nvidia-smi")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap",
             "--format=csv,noheader"],
            capture_output=True, text=True, check=True
        )
        print(f"  Result: {result.stdout.strip()}")

        if "5090" not in result.stdout:
            print("  WARNING: RTX 5090 not detected!")
            return False

        print("  PASSED")
        return True

    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def check_cuda_toolkit():
    """Verify CUDA toolkit is installed."""
    print("\n" + "=" * 60)
    print("STEP 2: CUDA Toolkit")
    print("=" * 60)

    try:
        result = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, check=True)
        for line in result.stdout.strip().split("\n"):
            if "release" in line.lower():
                print(f"  {line.strip()}")
        print("  PASSED")
        return True
    except Exception as e:
        print(f"  FAILED: nvcc not found. Install CUDA toolkit 12.8+ for full support.")
        print("  (Optional: PyTorch uses driver CUDA runtime, nvcc only needed for llama-cpp)")
        return False


def check_pytorch_cuda():
    """Verify PyTorch can access the GPU."""
    print("\n" + "=" * 60)
    print("STEP 3: PyTorch CUDA")
    print("=" * 60)

    try:
        import torch
        print(f"  PyTorch version: {torch.__version__}")
        print(f"  CUDA available: {torch.cuda.is_available()}")

        if not torch.cuda.is_available():
            print("  FAILED: PyTorch cannot see the GPU.")
            print("  Likely cause: PyTorch installed without CUDA support.")
            print("  Fix: reinstall with --index-url https://download.pytorch.org/whl/cu128")
            return False

        print(f"  CUDA version: {torch.version.cuda}")
        print(f"  Device name: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        print(f"  Compute capability: {props.major}.{props.minor}")
        print(f"  Total VRAM: {props.total_memory / (1024**3):.1f} GB")

        # Quick compute test
        print("\n  Running compute test...")
        a = torch.randn(4096, 4096, device="cuda")
        b = torch.randn(4096, 4096, device="cuda")
        torch.cuda.synchronize()

        start = time.time()
        for _ in range(10):
            c = torch.matmul(a, b)
        torch.cuda.synchronize()
        elapsed = time.time() - start

        tflops = (2 * 4096**3 * 10) / elapsed / 1e12
        print(f"  Matrix multiply (4096x4096, 10 iters): {elapsed:.3f}s ({tflops:.1f} TFLOPS)")
        print("  PASSED")
        return True

    except ImportError:
        print("  FAILED: PyTorch not installed")
        return False


def check_ollama():
    """Verify Ollama is running and accessible."""
    print("\n" + "=" * 60)
    print("STEP 4: Ollama")
    print("=" * 60)

    try:
        import requests
        resp = requests.get("http://localhost:11434/api/version", timeout=5)
        if resp.status_code == 200:
            print(f"  Ollama version: {resp.json().get('version', 'unknown')}")
            print("  PASSED")
            return True
        else:
            print(f"  Ollama responded with status {resp.status_code}")
            return False
    except Exception:
        print("  Ollama not running. Start it with: ollama serve")
        print("  This is not blocking — Ollama is needed for LLM inference.")
        return False


def check_sentence_transformers():
    """Verify sentence-transformers works on GPU."""
    print("\n" + "=" * 60)
    print("STEP 5: Sentence Transformers (Embedding)")
    print("=" * 60)

    try:
        from sentence_transformers import SentenceTransformer
        import torch

        print("  Loading bge-large-en-v1.5 (first run will download ~1.3 GB)...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer("BAAI/bge-large-en-v1.5", device=device)

        test_texts = [
            "Gold prices rose sharply after the Federal Reserve announced rate cuts.",
            "Central bank gold reserves increased by 200 tonnes in Q3 2024.",
        ]

        start = time.time()
        embeddings = model.encode(test_texts, normalize_embeddings=True)
        elapsed = time.time() - start

        print(f"  Embedding dimension: {embeddings.shape[1]}")
        print(f"  Encoded {len(test_texts)} texts in {elapsed:.3f}s")
        print(f"  Device: {model.device}")
        print("  PASSED")
        return True

    except ImportError:
        print("  FAILED: sentence-transformers not installed")
        return False
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def main():
    print("NEWS INTELLIGENCE — GPU & ENVIRONMENT VERIFICATION")
    print(f"Python: {sys.version}")
    print(f"Executable: {sys.executable}")
    print()

    results = {
        "nvidia_smi": check_nvidia_smi(),
        "cuda_toolkit": check_cuda_toolkit(),
        "pytorch_cuda": check_pytorch_cuda(),
        "ollama": check_ollama(),
        "sentence_transformers": check_sentence_transformers(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_critical_passed = True
    for name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")
        if name != "ollama" and name != "cuda_toolkit" and not passed:
            all_critical_passed = False

    if all_critical_passed:
        print("\nAll critical checks passed. Environment is ready.")
    else:
        print("\nSome critical checks failed. Fix the issues above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()

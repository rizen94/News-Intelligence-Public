"""
Benchmark LLM inference speed for each model configuration.
Run after pulling models via Ollama to establish baseline performance.

Usage: python scripts/benchmark_inference.py
"""

import os
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "api"))

from config.settings import MODELS, OLLAMA_HOST


def benchmark_model(model_name: str, prompt: str, num_runs: int = 3):
    """Benchmark a single model's inference speed."""
    import requests

    results = []

    for i in range(num_runs):
        start = time.time()
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 256,
                    "temperature": 0.7,
                }
            },
            timeout=300
        )
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            tokens_generated = data.get("eval_count", 0)
            tokens_per_second = tokens_generated / elapsed if elapsed > 0 else 0
            results.append({
                "run": i + 1,
                "elapsed_s": round(elapsed, 2),
                "tokens": tokens_generated,
                "tokens_per_s": round(tokens_per_second, 1),
            })
        else:
            results.append({"run": i + 1, "error": f"HTTP {resp.status_code}"})

    return results


def main():
    test_prompt = (
        "Analyze the following news scenario: "
        "The Federal Reserve has announced an unexpected 50 basis point rate cut while "
        "inflation remains above target. Provide a structured analysis in 3 short paragraphs."
    )

    import requests
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        available = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
    except Exception:
        print("Ollama not running. Start with: ollama serve")
        sys.exit(1)

    print("LLM INFERENCE BENCHMARK — News Intelligence")
    print("=" * 60)
    print(f"Available models: {', '.join(available) or 'none'}")
    print()

    models_to_test = {k: v for k, v in MODELS.items() if k != "embedding"}
    for role, model_name in models_to_test.items():
        if model_name not in available:
            print(f"{role} ({model_name}): NOT PULLED — skipping")
            print(f"  Pull with: ollama pull {model_name}")
            print()
            continue

        print(f"{role} ({model_name}):")
        results = benchmark_model(model_name, test_prompt)
        for r in results:
            if "error" in r:
                print(f"  Run {r['run']}: {r['error']}")
            else:
                print(f"  Run {r['run']}: {r['tokens']} tokens in {r['elapsed_s']}s "
                      f"({r['tokens_per_s']} tok/s)")
        print()

    # Unload models after benchmark
    for model_name in available:
        try:
            requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={"model": model_name, "keep_alive": 0},
                timeout=30
            )
        except Exception:
            pass

    print("Benchmark complete. All models unloaded.")


if __name__ == "__main__":
    main()

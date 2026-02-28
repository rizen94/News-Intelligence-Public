"""
Real-time resource monitoring display.
Run in a separate terminal during pipeline execution to watch resource usage.

Usage: python scripts/resource_monitor.py
"""

import os
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "api"))

from shared.llm.resource_manager import ResourceManager


def main():
    rm = ResourceManager()

    print("Resource Monitor — Press Ctrl+C to stop")
    print("=" * 70)

    try:
        while True:
            snapshot = rm.monitor()
            gpu = snapshot["gpu"]
            ram = snapshot["ram"]

            # Clear screen
            print("\033[H\033[J", end="")

            print(f"Workload: {snapshot['workload']}")
            print(f"Time: {time.strftime('%H:%M:%S')}")
            print()
            print(f"GPU: {gpu['name']}")
            print(f"  VRAM: {gpu['vram_used_gb']:.1f} / {gpu['vram_total_gb']:.1f} GB "
                  f"(budget: {gpu['vram_budget_gb']:.1f} GB)")

            vram_bar_len = 40
            vram_pct = gpu['vram_used_gb'] / gpu['vram_total_gb'] if gpu['vram_total_gb'] > 0 else 0
            vram_filled = int(vram_bar_len * vram_pct)
            vram_bar = "█" * vram_filled + "░" * (vram_bar_len - vram_filled)
            print(f"  [{vram_bar}] {vram_pct * 100:.0f}%")

            print(f"  Utilization: {gpu['utilization_pct']:.0f}%")
            print(f"  Temperature: {gpu['temperature_c']:.0f}°C")
            print()
            print("RAM:")
            print(f"  Used: {ram['used_gb']:.1f} / {ram['total_gb']:.1f} GB "
                  f"(budget: {ram['ram_budget_gb']:.1f} GB)")

            ram_pct = ram['used_gb'] / ram['total_gb'] if ram['total_gb'] > 0 else 0
            ram_filled = int(vram_bar_len * ram_pct)
            ram_bar = "█" * ram_filled + "░" * (vram_bar_len - ram_filled)
            print(f"  [{ram_bar}] {ram_pct * 100:.0f}%")
            print()
            print(f"Models loaded: {', '.join(snapshot['models_loaded']) or 'none'}")
            print(f"Models expected: {', '.join(snapshot['models_expected']) or 'none'}")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()

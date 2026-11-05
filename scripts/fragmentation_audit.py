#!/usr/bin/env python3
"""
Fragmentation Audit - score directories for consolidation opportunities.

Scoring axes (0-5, higher = worse fragmentation):
  D: Duplication - same patterns across files
  C: Cohesion    - how related are functions within each file  
  K: Coupling    - cross-file dependencies in the cluster
  F: Footprint   - how spread out is the import surface

Decision thresholds:
  D>=3 AND F<=2 -> Merge cluster
  D>=3 AND F>2  -> Extract shared infra, keep files separate
  D<2 AND C>=4  -> Keep as-is
"""
import ast
from pathlib import Path
from collections import Counter


def count_lines(filepath: Path) -> int:
    try:
        return sum(1 for _ in filepath.open(encoding="utf-8", errors="replace"))
    except Exception:
        return 0


def extract_functions(filepath: Path):
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return [], []
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return funcs, classes


def detect_patterns(filepath: Path):
    source = filepath.read_text(encoding="utf-8")
    lines = source.splitlines()
    patterns = []
    if "_ensure_init" in source or "lazy.*init" in source.lower():
        patterns.append("lazy_init")
    if "_lock" in source and "threading.Lock" in source:
        patterns.append("locking")
    if "Path(__file__)" in source:
        patterns.append("path_resolution")
    if "@wraps" in source or "functools.wraps" in source:
        patterns.append("decorator")
    if "jsonl" in source.lower():
        patterns.append("jsonl_writer")
    if "dataclass" in source:
        patterns.append("dataclass_model")
    # Env var loading — repeated across config/ shared/ services/
    env_vars = ["env_str", "env_bool", "env_int", "env_list", "get_env"]
    if any(v in source for v in env_vars):
        patterns.append("env_loading")
    # LRU cache — confirmed in 10+ files (config/, services/, shared/)
    if "lru_cache" in source or "@cache" in source:
        patterns.append("lru_cache")
    # DB connection import — the 'god import' anti-pattern
    if "get_db_connection" in source or "from shared.database" in source:
        patterns.append("db_import")
    # Dead code prefixes (retired/legacy/archive)
    name = filepath.name.lower()
    if any(name.startswith(p) for p in ("retired_", "legacy_", "archive_")):
        patterns.append("dead_code_prefix")
    # Large file flag (>500 lines — single-file complexity risk)
    if len(lines) > 500:
        patterns.append(f"large_file_{len(lines)}L")
    return patterns

def audit_cluster(cluster_path: Path):
    parts = cluster_path.parts[len(Path.cwd().parts) :]
    name = "/".join(parts) if parts else cluster_path.name
    py_files = sorted([f for f in cluster_path.glob("*.py") if f.name != "__init__.py"])
    
    if not py_files:
        return None

    all_funcs = Counter()
    all_patterns = Counter()
    total_lines = 0
    file_details = []
    import_sources = Counter()
    facade_adoption = Counter()  # tracks: 'facade' vs 'impl_detail' for shared.database imports

    for fpath in py_files:
        funcs, classes = extract_functions(fpath)
        lines = count_lines(fpath)
        total_lines += lines
        all_funcs.update(funcs)
        # Track import sprawl per file
        src = fpath.read_text(encoding="utf-8", errors="replace")
        for line in src.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("from ") or stripped.startswith("import ")):
                continue
            try:
                if " from " in stripped and stripped.startswith("from "):
                    mod = stripped.split(" from ")[-1].strip().split()[0]
                elif stripped.startswith("from ") and len(stripped) > 5:
                    # Catch all 'from X import Y' lines, even when nothing precedes 'from'
                    mod = stripped.split()[1]
                elif " import " in stripped and stripped.startswith("import "):
                    rest = stripped.split(" import ", 1)[1]
                    if "," in rest:
                        mod = rest.split(",")[0].strip()
                    else:
                        mod = rest.strip()
                else:
                    continue
                # Keep full path for facade tracking BEFORE collapsing to top-level
                full_mod = mod
                if "." in mod:
                    mod = mod.split(".")[0]
                if mod and not mod.startswith("_"):
                    import_sources[mod] += 1
                    # Track facade adoption for shared.database specifically
                    if full_mod == "shared.database":
                        facade_adoption["facade"] += 1
                    elif full_mod.startswith("shared.database."):
                        facade_adoption["impl_detail"] += 1
            except (IndexError, ValueError):
                continue
        file_details.append({
            "name": fpath.name,
            "lines": lines,
            "funcs": len(funcs),
            "classes": len(classes),
        })
        for p in detect_patterns(fpath):
            all_patterns[p] += 1

    # D: Duplication - count patterns appearing in >=3 files
    dup_count = sum(1 for pat, cnt in all_patterns.items() if cnt >= 3)
    duplication = min(5, max(0, dup_count + (1 if len(py_files) > 4 else 0)))

    # C: Cohesion - avg funcs per file; low=cohesive, high=incoherent
    avg_funcs = sum(fd["funcs"] for fd in file_details) / max(1, len(file_details))
    cohesion = min(5, max(0, 4 - int(avg_funcs / 3)))

    # K: Coupling - cross-references between files in cluster
    coupling_patterns = set()
    for fpath in py_files:
        src = fpath.read_text(encoding="utf-8", errors="replace")
        for other in py_files:
            if other == fpath:
                continue
            stem = other.stem.replace("logger", "").replace("_logger", "")
            if stem and (stem in str(fpath) or fpath.name in other.read_text(encoding="utf-8", errors="replace")):
                coupling_patterns.add((fpath.name, other.name))
    coupling = min(5, max(0, len(coupling_patterns)))

    # F: Footprint - ratio of public (non-_*) functions vs private
    public_count = sum(1 for f in all_funcs.keys() if not f.startswith("_"))
    total_count = max(1, len(all_funcs))
    footprint = min(5, int((public_count / total_count) * 4) + (1 if len(py_files) > 3 else 0))

    # Decision
    if duplication >= 3 and footprint <= 2:
        action = "MERGE cluster"
        reason = f"{duplication} dup patterns, {len(py_files)} files, low public API ({footprint})"
    elif duplication >= 3:
        action = "EXTRACT shared infra only"
        reason = f"High dup ({duplication}) but large public API ({footprint}) - extract common patterns only"
    elif cohesion >= 4:
        action = "KEEP as-is"
        reason = f"Low dup ({duplication}), cohesive functions (avg {avg_funcs:.1f} funcs/file)"
    else:
        action = "REVIEW manually"
        reason = f"Mixed: D={duplication} C={cohesion} K={coupling} F={footprint}"

    return {
        "cluster": name,
        "files": len(py_files),
        "lines": total_lines,
        "funcs": len(all_funcs),
        "details": file_details,
        "D": duplication,
        "C": cohesion,
        "K": coupling,
        "F": footprint,
        "action": action,
        "reason": reason,
        "shared_patterns": {k: v for k, v in all_patterns.items() if v >= 2},
        "import_sprawl": {k: v for k, v in import_sources.most_common(10)},
        "facade_adoption": dict(facade_adoption),
        "_scan_path": cluster_path,
    }


def main():
    root = Path.cwd() / "api"
    
    clusters_to_scan = [
        root / "shared",
        root / "modules" / "ml",
        root / "domains",
        root / "services",
        root / "config",
    ]

    results = []
    for cluster_path in clusters_to_scan:
        if not cluster_path.exists():
            continue
        result = audit_cluster(cluster_path)
        if result:
            results.append(result)

    # Print table
    print("=" * 120)
    print(f"{'Cluster':<30} {'Files':>5} {'Lines':>6} {'Funcs':>6} | D C K F | Action                        | Reason")
    print("-" * 120)

    for r in sorted(results, key=lambda x: x["D"], reverse=True):
        score = f"{r['D']} {r['C']} {r['K']} {r['F']}"
        action_pad = r["action"].ljust(26)
        reason_short = r["reason"][:50]
        print(f"{r['cluster']:<30} {r['files']:>5} {r['lines']:>6} {r['funcs']:>6} | {score:>4} | {action_pad:<26} | {reason_short}")

    # Detail each cluster's shared patterns + import sprawl
    print()
    for r in results:
        if r["shared_patterns"]:
            print(f"\n--- {r['cluster']} - Shared Patterns ---")
            for pat, cnt in sorted(r["shared_patterns"].items(), key=lambda x: -x[1]):
                print(f"  {pat}: {cnt} files")
        if r.get("import_sprawl"):
            print(f"\n--- {r['cluster']} - Import Sources (most common) ---")
            for src, cnt in list(r["import_sprawl"].items())[:6]:
                print(f"  from {src}: {cnt} files import it")
        if r.get("facade_adoption"):
            fa = r["facade_adoption"]
            total = fa.get("facade", 0) + fa.get("impl_detail", 0)
            pct = f"{100 * fa.get('facade', 0) / max(1, total):.0f}%" if total else "?"
            print(f"\n--- {r['cluster']} - DB Facade Adoption ---")
            print(f"  facade: {fa.get('facade', 0)}   impl_detail bypasses: {fa.get('impl_detail', 0)}   ({pct} through facade)")
        print(f"\n--- {r['cluster']} - File Detail ---")
        cluster_path = r.get("_scan_path", root)
        for fd in sorted(r["details"], key=lambda x: -x["lines"])[:15]:
            flags = ""
            target = cluster_path / fd["name"]
            if target.exists():
                found = [p for p in detect_patterns(target) if "large_file_" in p or "dead_code_" in p]
                if found:
                    flags = f" [{found[0]}]"
            print(f"    {fd['name']:40s} {fd['lines']:>5} lines  {fd['funcs']:>3} funcs{flags}")

    print("\n" + "=" * 120)


if __name__ == "__main__":
    main()

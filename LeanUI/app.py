#!/usr/bin/env python3
"""
QuantConnect LEAN - Interactive Web Dashboard
A comprehensive web UI for managing backtests, live trading, data, and configuration.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import shutil
from datetime import datetime
from glob import glob
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from algo_descriptions import describe_algorithm, scan_source_file

app = Flask(__name__)

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
LAUNCHER_DIR = BASE_DIR / "Launcher"
CONFIG_PATH = LAUNCHER_DIR / "config.json"
BIN_DIR = LAUNCHER_DIR / "bin" / "Debug"
ALGO_CSHARP_DIR = BASE_DIR / "Algorithm.CSharp"
ALGO_PYTHON_DIR = BASE_DIR / "Algorithm.Python"
DATA_DIR = BASE_DIR / "Data"
RESULTS_DIR = BIN_DIR / "results"
LOGS_DIR = BIN_DIR / "logs"

# Global state for running process
running_process = None
running_logs = []
log_event = threading.Event()


def load_config():
    """Load config.json, stripping JS-style comments"""
    with open(CONFIG_PATH, "r") as f:
        lines = f.readlines()

    # Strip line comments (// ...) but not inside strings (URLs like ws://)
    cleaned = []
    for line in lines:
        in_string = False
        in_char = None
        result = []
        i = 0
        while i < len(line):
            ch = line[i]
            if in_string:
                result.append(ch)
                if ch == in_char and (i == 0 or line[i-1] != "\\"):
                    in_string = False
                    in_char = None
            elif ch in ('"', "'"):
                in_string = True
                in_char = ch
                result.append(ch)
            elif ch == "/" and i + 1 < len(line) and line[i+1] == "/":
                # Line comment starts
                break
            else:
                result.append(ch)
            i += 1
        cleaned.append("".join(result))

    content = "".join(cleaned)
    return json.loads(content)


def save_config(config_dict):
    """Save config.json preserving format as much as possible"""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config_dict, f, indent=2)


def get_algorithms():
    """Discover available algorithms (C# and Python)"""
    algorithms = {"CSharp": [], "Python": []}

    # C# algorithms
    if ALGO_CSHARP_DIR.exists():
        for f in sorted(ALGO_CSHARP_DIR.glob("*.cs")):
            algorithms["CSharp"].append(
                {"name": f.stem, "file": f"{f.stem}.cs", "path": str(f), "language": "CSharp"}
            )

    # Python algorithms
    if ALGO_PYTHON_DIR.exists():
        for f in sorted(ALGO_PYTHON_DIR.glob("*.py")):
            algorithms["Python"].append(
                {"name": f.stem, "file": f"{f.stem}.py", "path": str(f), "language": "Python"}
            )

    return algorithms


def get_data_tree():
    """Get market data directory structure"""
    tree = {}
    if not DATA_DIR.exists():
        return tree

    for item in sorted(DATA_DIR.iterdir()):
        if item.is_dir():
            children = {}
            for sub in sorted(item.iterdir()):
                if sub.is_dir():
                    grandchildren = {}
                    for leaf in sorted(sub.iterdir()):
                        if leaf.is_dir():
                            files = [f.name for f in sorted(leaf.iterdir()) if f.is_file()]
                            grandchildren[leaf.name] = files
                    if grandchildren:
                        children[sub.name] = grandchildren
            if children:
                tree[item.name] = children
    return tree


def get_recent_logs(count=200):
    """Get recent log entries from the logs directory"""
    log_files = []
    if LOGS_DIR.exists():
        log_files = sorted(LOGS_DIR.glob("*.txt"), key=os.path.getmtime, reverse=True)

    lines = []
    for lf in log_files[:3]:
        try:
            with open(lf, "r") as f:
                content = f.read()
                lines.extend(content.strip().split("\n")[-count:])
        except Exception:
            pass
    return lines[-count:] if len(lines) > count else lines


def get_results():
    """Get list of backtest results"""
    results = []
    if RESULTS_DIR.exists():
        for d in sorted(RESULTS_DIR.iterdir(), reverse=True):
            if d.is_dir():
                result = {"name": d.name, "path": str(d), "files": []}
                for f in sorted(d.iterdir()):
                    result["files"].append(
                        {"name": f.name, "size": f.stat().st_size if f.is_file() else 0}
                    )
                results.append(result)
    return results


def get_system_info():
    """Get system information"""
    dotnet_version = ""
    try:
        r = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, timeout=10)
        dotnet_version = r.stdout.strip()
    except Exception:
        dotnet_version = "not found"

    python_version = sys.version.split()[0]

    # Check Lean version
    lean_version = "unknown"
    try:
        for line in (BIN_DIR / "QuantConnect.Lean.Launcher.deps.json").read_text().split("\n")[:1]:
            pass
    except Exception:
        pass

    return {
        "dotnet": dotnet_version,
        "python": python_version,
        "os": sys.platform,
        "lean_version": "2.5.0",
        "project_dir": str(BASE_DIR),
        "data_dir": str(DATA_DIR),
        "data_exists": DATA_DIR.exists(),
    }


# ============================================================
# API Routes
# ============================================================

@app.route("/api/algorithms")
def api_algorithms():
    search = request.args.get("search", "").lower()
    lang = request.args.get("language", "")
    algorithms = get_algorithms()

    if lang and lang in algorithms:
        result = algorithms[lang]
        for a in result:
            a["language"] = lang
    else:
        result = algorithms

    if search:
        if isinstance(result, dict):
            filtered = {}
            for l, items in result.items():
                matched = [a for a in items if search in a["name"].lower()]
                if matched:
                    filtered[l] = matched
            result = filtered
        else:
            result = [a for a in result if search in a["name"].lower()]

    return jsonify(result)


@app.route("/api/algorithms/describe/<algo_name>")
def api_algorithm_detail(algo_name):
    """Get detailed Chinese description for a specific algorithm"""
    lang = request.args.get("language", "CSharp")
    # Determine source file path
    if lang == "Python":
        src_path = ALGO_PYTHON_DIR / f"{algo_name}.py"
    else:
        src_path = ALGO_CSHARP_DIR / f"{algo_name}.cs"

    # Generate description
    desc = describe_algorithm(algo_name)

    # Try to scan source for more details
    if src_path.exists():
        extra = scan_source_file(src_path)
        desc.update(extra)

    # Get source preview
    if src_path.exists():
        try:
            source = src_path.read_text(encoding="utf-8", errors="ignore")
            desc["source_preview"] = source[:3000]
            desc["source_lines"] = len(source.split("\n"))
        except Exception:
            pass

    desc["file_path"] = str(src_path) if src_path.exists() else ""
    desc["file_exists"] = src_path.exists()

    return jsonify(desc)


@app.route("/api/algorithms/descriptions")
def api_algorithm_descriptions():
    """Get Chinese descriptions for all algorithms (paginated)"""
    algorithms = get_algorithms()
    all_descs = {}

    for lang, algos in algorithms.items():
        all_descs[lang] = []
        for a in algos[:100]:  # Limit to first 100 per language for performance
            desc = describe_algorithm(a["name"])
            all_descs[lang].append({
                "name": a["name"],
                "file": a["file"],
                "cn_title": desc["cn_title"],
                "description": desc["description"],
                "category": desc["category"],
                "difficulty": desc["difficulty"],
            })

    return jsonify(all_descs)


# ---- Tags / Bookmarks ----
TAGS_FILE = BASE_DIR / ".lean_tags.json"


def load_tags():
    if TAGS_FILE.exists():
        try:
            return json.loads(TAGS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_tags_file(tags):
    TAGS_FILE.write_text(json.dumps(tags, indent=2, ensure_ascii=False))


@app.route("/api/tags")
def api_get_tags():
    return jsonify(load_tags())


@app.route("/api/tags", methods=["POST"])
def api_save_tags():
    try:
        tags = request.get_json()
        save_tags_file(tags)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---- Batch Backtest ----
batch_tasks = {}
batch_lock = threading.Lock()


@app.route("/api/batch/run", methods=["POST"])
def api_batch_run():
    """Run backtests for multiple algorithms sequentially"""
    data = request.get_json()
    algos = data.get("algorithms", [])  # [{name, language}]
    environment = data.get("environment", "backtesting")

    if not algos:
        return jsonify({"status": "error", "message": "No algorithms selected"}), 400

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_tasks[batch_id] = {
        "id": batch_id,
        "total": len(algos),
        "completed": 0,
        "running": True,
        "results": [],
        "current": None,
    }

    def run_batch():
        env = os.environ.copy()
        if "PYTHONNET_PYDLL" not in env:
            venv_python = BASE_DIR / ".venv" / "bin" / "python3"
            python_bin = str(venv_python) if venv_python.exists() else sys.executable
            try:
                result = subprocess.run(
                    [python_bin, "-c",
                     "import sys; v=f'{sys.version_info.major}.{sys.version_info.minor}'; print(v)"],
                    capture_output=True, text=True, timeout=5)
                pyver = result.stdout.strip()
                for search_root in ["/opt/homebrew", "/usr/local"]:
                    found = list(Path(search_root).rglob(f"libpython{pyver}.dylib"))
                    if found:
                        env["PYTHONNET_PYDLL"] = str(found[0])
                        break
            except Exception:
                pass

        for i, algo in enumerate(algos):
            algo_name = algo["name"]
            algo_lang = algo.get("language", "CSharp")

            # Update config for this algorithm
            config = load_config()
            config["algorithm-type-name"] = algo_name
            config["algorithm-language"] = algo_lang
            config["environment"] = environment
            if algo_lang == "Python":
                config["algorithm-location"] = f"../../../Algorithm.Python/{algo_name}.py"
            else:
                config["algorithm-location"] = "QuantConnect.Algorithm.CSharp.dll"
            save_config(config)

            batch_tasks[batch_id]["current"] = algo_name

            try:
                proc = subprocess.run(
                    ["dotnet", "QuantConnect.Lean.Launcher.dll"],
                    cwd=str(BIN_DIR),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env=env,
                )
                output = proc.stdout + "\n" + proc.stderr

                # Parse statistics
                stats = {}
                for line in output.split("\n"):
                    line = line.strip()
                    if line.startswith("STATISTICS::"):
                        parts = line.replace("STATISTICS::", "").strip().split(None, 1)
                        if len(parts) >= 2:
                            stats[parts[0].strip()] = parts[1].strip()

                batch_tasks[batch_id]["results"].append({
                    "name": algo_name,
                    "language": algo_lang,
                    "success": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stats": stats,
                    "error": output[-500:] if proc.returncode != 0 else None,
                })
            except subprocess.TimeoutExpired:
                batch_tasks[batch_id]["results"].append({
                    "name": algo_name,
                    "language": algo_lang,
                    "success": False,
                    "exit_code": -1,
                    "stats": {},
                    "error": "Timeout (120s)",
                })
            except Exception as e:
                batch_tasks[batch_id]["results"].append({
                    "name": algo_name,
                    "language": algo_lang,
                    "success": False,
                    "exit_code": -1,
                    "stats": {},
                    "error": str(e),
                })

            batch_tasks[batch_id]["completed"] = i + 1

        batch_tasks[batch_id]["running"] = False
        batch_tasks[batch_id]["current"] = None

    thread = threading.Thread(target=run_batch, daemon=True)
    thread.start()

    return jsonify({"status": "started", "batch_id": batch_id, "total": len(algos)})


@app.route("/api/batch/status/<batch_id>")
def api_batch_status(batch_id):
    task = batch_tasks.get(batch_id)
    if not task:
        return jsonify({"status": "error", "message": "Batch not found"}), 404

    # Sort results by Sharpe ratio if available
    results = task.get("results", [])
    ranked = sorted(
        results,
        key=lambda r: float(r.get("stats", {}).get("Sharpe Ratio", "-9999").replace("%", "") or "-9999"),
        reverse=True,
    )
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return jsonify({
        "id": task["id"],
        "total": task["total"],
        "completed": task["completed"],
        "running": task["running"],
        "current": task["current"],
        "results": ranked,
    })


@app.route("/api/batch/stop/<batch_id>", methods=["POST"])
def api_batch_stop(batch_id):
    task = batch_tasks.get(batch_id)
    if task:
        task["running"] = False
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Batch not found"}), 404


@app.route("/api/config")
def api_config():
    config = load_config()
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def api_config_update():
    try:
        new_config = request.get_json()
        save_config(new_config)
        return jsonify({"status": "ok", "message": "Configuration saved"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/system")
def api_system():
    return jsonify(get_system_info())


@app.route("/api/data-tree")
def api_data_tree():
    return jsonify(get_data_tree())


@app.route("/api/logs")
def api_logs():
    count = request.args.get("count", 200, type=int)
    return jsonify({"logs": get_recent_logs(count)})


@app.route("/api/results")
def api_results():
    return jsonify(get_results())


@app.route("/api/backtest/run", methods=["POST"])
def api_backtest_run():
    global running_process, running_logs
    data = request.get_json()
    algorithm_name = data.get("algorithm", "BasicTemplateFrameworkAlgorithm")
    language = data.get("language", "CSharp")
    environment = data.get("environment", "backtesting")

    # Update config
    config = load_config()
    config["environment"] = environment
    config["algorithm-type-name"] = algorithm_name
    config["algorithm-language"] = language

    if language == "Python":
        config["algorithm-location"] = f"../../../Algorithm.Python/{algorithm_name}.py"
    else:
        config["algorithm-location"] = "QuantConnect.Algorithm.CSharp.dll"

    save_config(config)

    running_logs = []
    log_event.clear()

    def run_backtest():
        global running_process, running_logs
        env = os.environ.copy()
        # Set PYTHONNET_PYDLL for Python algorithm support
        if "PYTHONNET_PYDLL" not in env:
            import platform
            if platform.system() == "Darwin":
                # Try to find libpython on macOS
                venv_python = BASE_DIR / ".venv" / "bin" / "python3"
                python_bin = str(venv_python) if venv_python.exists() else sys.executable
                try:
                    result = subprocess.run(
                        [python_bin, "-c",
                         "import sys; v=f'{sys.version_info.major}.{sys.version_info.minor}'; print(v)"],
                        capture_output=True, text=True, timeout=5)
                    pyver = result.stdout.strip()
                    # Search common paths
                    for search_root in ["/opt/homebrew", "/usr/local"]:
                        found = list(Path(search_root).rglob(f"libpython{pyver}.dylib"))
                        if found:
                            env["PYTHONNET_PYDLL"] = str(found[0])
                            break
                except Exception:
                    pass
        try:
            proc = subprocess.Popen(
                ["dotnet", "run", "--project", str(LAUNCHER_DIR / "QuantConnect.Lean.Launcher.csproj")],
                cwd=str(BIN_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            running_process = proc
            for line in iter(proc.stdout.readline, ""):
                running_logs.append(line.rstrip())
                log_event.set()
                if len(running_logs) > 5000:
                    running_logs = running_logs[-3000:]
            proc.wait()
        except Exception as e:
            running_logs.append(f"ERROR: {str(e)}")
        finally:
            running_process = None
            log_event.set()

    thread = threading.Thread(target=run_backtest, daemon=True)
    thread.start()

    return jsonify({"status": "started", "message": f"Backtest started: {algorithm_name}"})


@app.route("/api/backtest/status")
def api_backtest_status():
    global running_process
    is_running = running_process is not None and running_process.poll() is None
    return jsonify({
        "running": is_running,
        "exit_code": running_process.returncode if running_process and running_process.poll() is not None else None,
    })


@app.route("/api/backtest/stop", methods=["POST"])
def api_backtest_stop():
    global running_process
    if running_process and running_process.poll() is None:
        running_process.terminate()
        return jsonify({"status": "ok", "message": "Terminating backtest..."})
    return jsonify({"status": "error", "message": "No backtest running"})


@app.route("/api/backtest/logs/stream")
def api_backtest_logs_stream():
    global running_logs
    since = request.args.get("since", 0, type=int)
    timeout = request.args.get("timeout", 30, type=int)

    # Wait for new logs if needed
    waited = 0
    while len(running_logs) <= since and running_process and running_process.poll() is None:
        if waited >= timeout:
            break
        log_event.wait(timeout=1)
        log_event.clear()
        waited += 1

    new_logs = running_logs[since:]
    return jsonify(
        {
            "logs": new_logs,
            "total": len(running_logs),
            "running": running_process is not None and running_process.poll() is None,
        }
    )


@app.route("/api/backtest/results")
def api_backtest_results():
    """Parse and return backtest result summary"""
    results = {}
    if not RESULTS_DIR.exists():
        return jsonify(results)

    dirs = sorted(RESULTS_DIR.iterdir(), key=os.path.getmtime, reverse=True)
    if not dirs:
        return jsonify(results)

    latest = dirs[0]
    # Try to find order/statistics files
    for f in latest.iterdir():
        if f.suffix == ".json":
            try:
                with open(f) as fp:
                    results[f.stem] = json.load(fp)
            except Exception:
                pass
        elif f.suffix in (".txt", ".csv", ".log"):
            try:
                with open(f) as fp:
                    results[f.stem] = fp.read()[:5000]
            except Exception:
                pass

    results["_path"] = str(latest)
    results["_name"] = latest.name
    return jsonify(results)


@app.route("/api/results/<path:filepath>")
def api_result_file(filepath):
    """Serve result files"""
    full_path = RESULTS_DIR / filepath
    if not full_path.exists():
        return "File not found", 404
    return send_from_directory(str(RESULTS_DIR), filepath)


# ============================================================
# Frontend Routes
# ============================================================

@app.route("/")
def index():
    algorithms = get_algorithms()
    config = load_config()
    system = get_system_info()
    return render_template(
        "index.html",
        algorithms=algorithms,
        config=config,
        system=system,
    )


if __name__ == "__main__":
    print(f"Starting Lean Dashboard...")
    print(f"Project: {BASE_DIR}")
    print(f"Open http://localhost:5555 in your browser")
    app.run(host="0.0.0.0", port=5555, debug=True)

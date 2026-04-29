from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).parent.resolve()
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.transpiler.core.errors import TranspilerError  # noqa: E402
from src.python_to_java.service import PythonToJavaCompilerService  # noqa: E402


app = Flask(__name__)
service = PythonToJavaCompilerService(project_root=ROOT)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/transpile")
def api_transpile():
    payload = request.get_json(silent=True) or {}
    source_code = payload.get("source_code") or ""

    if not source_code.strip():
        return jsonify({"ok": False, "error": "Source code cannot be empty."}), 400

    try:
        result = service.translate(source_code)
    except TranspilerError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:  # defensive guard
        return jsonify({"ok": False, "error": f"Unexpected server error: {exc}"}), 500

    return jsonify(
        {
            "ok": True,
            "target_code": result.java_code,
            "semantic_match": result.semantic_match,
            "logs_path": str(result.logs_path) if result.logs_path else None,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

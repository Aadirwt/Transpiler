from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.transpiler.core.errors import TranspilerError  # noqa: E402
from src.python_to_java.service import PythonToJavaCompilerService  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Python-to-Java translator with validation, logging, and auto-correction."
    )
    parser.add_argument("--input", dest="input_path", required=True, type=Path)
    parser.add_argument("--output", dest="output_path", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = args.input_path.read_text(encoding="utf-8-sig")
    service = PythonToJavaCompilerService(project_root=ROOT)

    try:
        result = service.translate(source)
    except TranspilerError as exc:
        print(f"Error: {exc}")
        return 1

    args.output_path.write_text(result.java_code, encoding="utf-8")
    print(f"Wrote target code: {args.output_path}")
    print(f"Semantic match: {result.semantic_match}")
    if result.logs_path:
        print(f"Log file: {result.logs_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

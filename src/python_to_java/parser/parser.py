from __future__ import annotations

from src.transpiler.frontends.python_frontend import PythonFrontend

from ..models import ParsedPythonModule, PreprocessedInput


class Parser:
    def __init__(self) -> None:
        self.frontend = PythonFrontend()

    def parse(self, preprocessed: PreprocessedInput) -> ParsedPythonModule:
        ast = self.frontend.parse(preprocessed.code)
        return ParsedPythonModule(
            source=preprocessed.code,
            imports=preprocessed.imports,
            ast=ast,
        )

from __future__ import annotations

from src.transpiler.backends.java_backend import JavaBackend
from src.transpiler.core.tac import TACProgram

from ..mapper import FunctionMapper, LibraryMapper
from ..models import ImportSpec


class CodeGenerator:
    def __init__(self) -> None:
        self.function_mapper = FunctionMapper()
        self.library_mapper = LibraryMapper()

    def generate(self, ir: TACProgram, imports: list[ImportSpec]) -> str:
        backend = JavaBackend(
            function_mapper=self.function_mapper,
            library_mapper=self.library_mapper,
        )
        backend.set_source_imports(imports)
        return backend.generate(ir)

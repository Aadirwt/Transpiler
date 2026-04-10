from __future__ import annotations

from dataclasses import dataclass

from .backends import JavaBackend
from .core.errors import BackendError
from .core.optimizer import TACOptimizer
from .core.semantic import SemanticAnalyzer
from .core.tac import TACProgram
from .core.tac_generator import TACGenerator
from .frontends import PythonFrontend


@dataclass
class PipelineResult:
    code: str
    tac: TACProgram


class TranspilerPipeline:
    def __init__(self) -> None:
        self.frontends = {
            "python": PythonFrontend(),
        }
        self.backends = {
            "java": JavaBackend(),
        }
        self.optimizer = TACOptimizer()

    def transpile(self, source: str, source_lang: str, target_lang: str) -> PipelineResult:
        src = source_lang.lower()
        dst = target_lang.lower()

        if src not in self.frontends:
            raise BackendError(
                f"Unsupported source language '{source_lang}'. Only Python source is supported."
            )
        if dst not in self.backends:
            raise BackendError(
                f"Unsupported target language '{target_lang}'. Only Java is supported."
            )

        frontend = self.frontends[src]
        backend = self.backends[dst]

        ast = frontend.parse(source)
        SemanticAnalyzer(source_language="python").analyze(ast)
        tac = self.optimizer.optimize(TACGenerator().generate(ast))
        code = backend.generate(tac)
        return PipelineResult(code=code, tac=tac)

from __future__ import annotations

from src.transpiler.core.optimizer import TACOptimizer
from src.transpiler.core.tac import TACProgram
from src.transpiler.core.tac_generator import TACGenerator


class Transformer:
    def __init__(self) -> None:
        self.generator = TACGenerator()
        self.optimizer = TACOptimizer()

    def transform(self, ast) -> TACProgram:
        return self.optimizer.optimize(self.generator.generate(ast))

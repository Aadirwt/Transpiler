from __future__ import annotations

from pathlib import Path

from src.transpiler.backends.java_backend import JavaBackend
from src.transpiler.core.optimizer import TACOptimizer
from src.transpiler.core.semantic import SemanticAnalyzer
from src.transpiler.core.symbol_table import SymbolTableBuilder
from src.transpiler.core.tac_generator import TACGenerator
from src.transpiler.core.type_inferencer import TypeInferencer
from src.transpiler.frontends.python_frontend import PythonFrontend

from .autocorrect import AutoCorrector
from .checker import SemanticChecker
from .execution import ExecutionEngine
from .input import InputHandler
from .logger import Reporter
from .models import TranslationResult


class PythonToJavaCompilerService:
    def __init__(self, project_root: Path | None = None, max_retries: int = 2) -> None:
        self.input_handler = InputHandler()
        self.frontend = PythonFrontend()
        self.tac_generator = TACGenerator()
        self.optimizer = TACOptimizer()
        self.execution = ExecutionEngine()
        self.checker = SemanticChecker()
        self.auto_corrector = AutoCorrector()
        self.reporter = Reporter(project_root or Path.cwd())
        self.max_retries = max_retries

    def translate(self, source_code: str) -> TranslationResult:
        preprocessed = self.input_handler.preprocess(source_code)
        ast = self.frontend.parse(preprocessed.code)
        SemanticAnalyzer(source_language="python").analyze(ast)
        TypeInferencer().infer(ast)
        symbol_builder = SymbolTableBuilder()
        symbol_builder.build(ast)
        tac = self.optimizer.optimize(self.tac_generator.generate(ast))
        backend = JavaBackend()
        backend.set_source_imports(preprocessed.imports)
        java_code = backend.generate(tac)

        result = TranslationResult(java_code=java_code, tac=tac)
        result.diagnostics.extend(preprocessed.warnings)
        result.diagnostics.extend(backend.library_mapper.warnings_for(preprocessed.imports))
        result.symbol_table = symbol_builder.to_text()
        result.typed_ast = repr(ast)
        python_run = self.execution.run_python(source_code)
        result.python_output = python_run.stdout if python_run.success else python_run.stderr

        for attempt in range(self.max_retries + 1):
            java_run = self.execution.run_java(result.java_code)
            result.retries = attempt
            if java_run.success:
                result.java_output = java_run.stdout
                result.semantic_match = self.checker.compare(
                    source_code,
                    result.python_output,
                    result.java_output,
                )
                break

            result.correction_history.append(java_run.stderr.strip())
            corrected = self.auto_corrector.fix(result.java_code, java_run.stderr)
            if corrected == result.java_code:
                result.java_output = java_run.stderr
                result.semantic_match = False
                break
            result.java_code = corrected
        else:
            result.semantic_match = False

        status = "passed" if result.semantic_match else "needs_attention"
        result.logs_path = self.reporter.log(source_code, result, status)
        return result

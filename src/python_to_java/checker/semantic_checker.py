from __future__ import annotations

import re


class SemanticChecker:
    def compare(self, source_code: str, py_out: str, java_out: str) -> bool:
        py_clean = py_out.strip()
        java_clean = java_out.strip()

        if py_clean == java_clean:
            return True

        randint_ranges = self._randint_ranges(source_code)
        if randint_ranges:
            return self._compare_randint_outputs(py_clean, java_clean, randint_ranges)

        return False

    def _randint_ranges(self, source_code: str) -> list[tuple[int, int]]:
        matches = re.findall(r"random\.randint\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", source_code)
        return [(int(start), int(end)) for start, end in matches]

    def _compare_randint_outputs(
        self,
        py_out: str,
        java_out: str,
        randint_ranges: list[tuple[int, int]],
    ) -> bool:
        py_lines = [line.strip() for line in py_out.splitlines() if line.strip()]
        java_lines = [line.strip() for line in java_out.splitlines() if line.strip()]

        if len(py_lines) != len(java_lines):
            return False
        if len(py_lines) != len(randint_ranges):
            return False

        for index, (py_line, java_line) in enumerate(zip(py_lines, java_lines)):
            if not re.fullmatch(r"-?\d+", py_line):
                return False
            if not re.fullmatch(r"-?\d+", java_line):
                return False

            low, high = randint_ranges[index]
            py_value = int(py_line)
            java_value = int(java_line)
            if not (low <= py_value <= high and low <= java_value <= high):
                return False

        return True

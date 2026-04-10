import unittest

from src.python_to_java.service import PythonToJavaCompilerService


class TestPythonToJavaService(unittest.TestCase):
    def test_class_constructor_uses_new_and_matches(self):
        code = """
class Counter:
    def __init__(self, start):
        self.value = start

    def bump(self, steps):
        total = self.value
        for i in range(0, steps, 1):
            total = total + 1
        self.value = total
        return self.value

c = Counter(2)
print(c.bump(3))
"""
        result = PythonToJavaCompilerService().translate(code)
        self.assertTrue(result.semantic_match)
        self.assertIn("new Counter(2)", result.java_code)

    def test_append_and_len_round_trip(self):
        code = """
lst = [1, 2]
lst.append(3)
print(len(lst))
"""
        result = PythonToJavaCompilerService().translate(code)
        self.assertTrue(result.semantic_match)
        self.assertIn("lst.add(3);", result.java_code)

    def test_math_library_mapping(self):
        code = """
import math
x = math.sqrt(16)
print(x)
"""
        result = PythonToJavaCompilerService().translate(code)
        self.assertTrue(result.semantic_match)
        self.assertIn("Math.sqrt", result.java_code)

    def test_random_randint_is_treated_as_valid_nondeterministic_output(self):
        code = """
import random
print(random.randint(0, 9))
"""
        result = PythonToJavaCompilerService().translate(code)
        self.assertTrue(result.semantic_match)
        self.assertIn("randomIntHelper", result.java_code)


if __name__ == "__main__":
    unittest.main()

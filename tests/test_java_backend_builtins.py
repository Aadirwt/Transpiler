import unittest
from src.python_to_java.service import PythonToJavaCompilerService

class TestJavaBuiltins(unittest.TestCase):
    def test_sort_and_list_translation(self):
        py_code = """
lst = [3, 1, 2]
sort(lst)
print(len(lst))
        """
        result = PythonToJavaCompilerService().translate(py_code)
        java_code = result.java_code
        self.assertIn("Collections.sort", java_code)
        self.assertIn("import java.util.Collections;", java_code)
        self.assertIn("ArrayList<Integer> lst", java_code)
        self.assertTrue(result.semantic_match)

if __name__ == "__main__":
    unittest.main()

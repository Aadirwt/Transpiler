# Python-to-Java Transpiler

A powerful, robust compiler project that translates Python code into structurally and semantically equivalent Java code. Unlike standard transpilers, this project goes a step further by utilizing an execution engine, semantic comparison, and an auto-correction loop to guarantee the resulting Java code behaves exactly like the original Python script.

## Features

- **Custom Compiler Pipeline**: Implements a full compiler architecture from scratch, including Lexing, Parsing, Abstract Syntax Tree (AST) generation, Semantic Analysis, Three-Address Code (TAC) generation, and Optimization.
- **Auto-Correction Engine**: If the generated Java code fails to compile or run (e.g., missing imports like `Scanner`), the system automatically detects the error, patches the Java code, and attempts to recompile it.
- **Semantic Validation**: Safely executes the original Python code in a sandbox, then compares its output against the executed Java code to guarantee mathematical and semantic equivalence.
- **Dual Interfaces**:
  - **Web Application**: A sleek Flask-based web interface for translating code on the fly.
  - **CLI Tool**: A command-line tool for file-to-file translation.

## Project Architecture

The compiler pipeline is organized in `src/` and consists of several crucial phases:

1. **Frontend (`src/transpiler/frontends`)**:
   - `lexer.py`: Tokenizes the raw Python code.
   - `parser.py`: Generates the Abstract Syntax Tree (AST).
2. **Core / Middle-End (`src/transpiler/core`)**:
   - `semantic.py`: Ensures type validity and scoping.
   - `tac_generator.py` & `optimizer.py`: Converts the AST to an intermediate Three-Address Code (TAC) and optimizes it.
3. **Backend (`src/transpiler/backends`)**:
   - `java_backend.py`: Translates the optimized TAC instructions into standard Java code.
4. **Validation & Execution (`src/python_to_java`)**:
   - `execution_engine.py`: Runs code in sandbox environments.
   - `semantic_checker.py`: Validates output equivalency.
   - `auto_corrector.py`: Fixes common generated code errors on the fly.

## Getting Started

### Prerequisites

- Python 3.8+
- Java JDK 8+ (ensure `java` and `javac` are added to your system's PATH)

### Installation

Clone the repository and (optionally) set up a virtual environment:
```bash
git clone https://github.com/Aadirwt/Transpiler.git
cd Transpiler
```

*Note: The project requires `Flask` for the web interface.*
```bash
pip install flask
```

### Usage

**1. Web Interface**
To start the web application, simply run:
```bash
python web_app.py
```
Then navigate to `http://127.0.0.1:5000` in your browser.

**2. Command Line Interface**
To translate a specific Python file to a Java file:
```bash
python main.py --input path/to/source.py --output path/to/output.java
```


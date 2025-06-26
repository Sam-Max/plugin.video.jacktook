import ast
import os
import sys

# Disallowed base names used as generics in Python < 3.9
PEP585_TYPES = {"list", "dict", "set", "tuple", "frozenset", "type", "callable"}

# PEP 593, 604, 647, 612, 673 keywords
UNSUPPORTED_NAMES = {
    "Annotated", "Self", "TypeGuard", "ParamSpec", "Concatenate", "Required", "NotRequired"
}

def find_incompatible_syntax(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError as e:
            return [("SYNTAX ERROR", e.lineno, str(e))]

    issues = []

    class Visitor(ast.NodeVisitor):
        def visit_BinOp(self, node):
            # Check for union types (e.g., int | None)
            if isinstance(node.op, ast.BitOr):
                issues.append(("Union | syntax", node.lineno, "Use Union[...] instead of |"))
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            if isinstance(node.annotation, ast.Subscript):
                base = node.annotation.value
                if isinstance(base, ast.Name) and base.id.lower() in PEP585_TYPES:
                    issues.append(("PEP 585 generic", node.lineno, f"Use typing.{base.id.capitalize()} instead"))
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            for arg in node.args.args + node.args.kwonlyargs:
                if isinstance(arg.annotation, ast.Subscript):
                    base = arg.annotation.value
                    if isinstance(base, ast.Name) and base.id.lower() in PEP585_TYPES:
                        issues.append(("PEP 585 generic", node.lineno, f"Use typing.{base.id.capitalize()} instead"))
            if isinstance(node.returns, ast.Subscript):
                base = node.returns.value
                if isinstance(base, ast.Name) and base.id.lower() in PEP585_TYPES:
                    issues.append(("PEP 585 generic", node.lineno, f"Use typing.{base.id.capitalize()} instead"))
            self.generic_visit(node)

        def visit_Match(self, node):
            issues.append(("match-case", node.lineno, "Structural pattern matching not supported in Python 3.7"))
            self.generic_visit(node)

        def visit_Name(self, node):
            if node.id in UNSUPPORTED_NAMES:
                issues.append((f"Unsupported typing: {node.id}", node.lineno, f"Requires typing_extensions or Python >= 3.8/3.10"))
            self.generic_visit(node)

    Visitor().visit(tree)
    return issues

def scan_project(root_path):
    results = []
    for dirpath, _, filenames in os.walk(root_path):
        for file in filenames:
            if file.endswith(".py"):
                filepath = os.path.join(dirpath, file)
                issues = find_incompatible_syntax(filepath)
                for kind, lineno, message in issues:
                    results.append((filepath, lineno, kind, message))
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_py37_compat.py /path/to/project")
        sys.exit(1)

    root = sys.argv[1]
    findings = scan_project(root)

    if not findings:
        print("✅ No Python 3.7 incompatibilities found.")
    else:
        print("❌ Found potential Python 3.7 incompatibilities:\n")
        for path, line, kind, msg in findings:
            print(f"{path}:{line} [{kind}] {msg}")

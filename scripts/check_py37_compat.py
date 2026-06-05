import ast
import os
import sys

# Disallowed base names used as generics in Python < 3.9
PEP585_TYPES = {"list", "dict", "set", "tuple", "frozenset", "type", "callable"}
PEP585_REPLACEMENTS = {
    "list": "List",
    "dict": "Dict",
    "set": "Set",
    "tuple": "Tuple",
    "frozenset": "FrozenSet",
    "type": "Type",
    "callable": "Callable",
}

# PEP 593, 604, 647, 612, 673 keywords
UNSUPPORTED_NAMES = {
    "Annotated", "Self", "TypeGuard", "ParamSpec", "Concatenate", "Required", "NotRequired"
}

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".agent",
    ".agents",
    ".opencode",
    ".worktrees",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
}

EXCLUDED_PATH_PARTS = {
    ("lib", "vendor"),
    ("lib", "api", "tmdbv3api"),
}


def is_excluded_path(path):
    normalized = os.path.normpath(path)
    path_parts = normalized.split(os.sep)
    parts = set(path_parts)
    if parts & EXCLUDED_DIRS:
        return True
    return any(has_path_parts(path_parts, excluded) for excluded in EXCLUDED_PATH_PARTS)


def has_path_parts(path_parts, excluded_parts):
    excluded_len = len(excluded_parts)
    return any(
        tuple(path_parts[index : index + excluded_len]) == excluded_parts
        for index in range(len(path_parts) - excluded_len + 1)
    )


def iter_annotation_nodes(annotation):
    if annotation is None:
        return
    yield annotation
    for child in ast.iter_child_nodes(annotation):
        yield from iter_annotation_nodes(child)


def is_pep585_annotation(annotation):
    return (
        isinstance(annotation, ast.Subscript)
        and isinstance(annotation.value, ast.Name)
        and annotation.value.id in PEP585_TYPES
    )


def unsupported_typing_name(node):
    if isinstance(node, ast.Name) and node.id in UNSUPPORTED_NAMES:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in UNSUPPORTED_NAMES:
        return node.attr
    return None


def pep585_message(base_name):
    replacement = PEP585_REPLACEMENTS.get(base_name, base_name.capitalize())
    return f"Use typing.{replacement} instead of built-in {base_name}[...]"


def check_annotation(annotation, issues):
    for node in iter_annotation_nodes(annotation):
        if is_pep585_annotation(node):
            base_name = node.value.id
            issues.append(("PEP 585 generic", node.lineno, pep585_message(base_name)))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            issues.append(("Union | syntax", node.lineno, "Use Union[...] instead of | in annotations"))
        unsupported_name = unsupported_typing_name(node)
        if unsupported_name is not None:
            issues.append(
                (
                    f"Unsupported typing: {unsupported_name}",
                    node.lineno,
                    "Requires typing_extensions or a newer Python runtime",
                )
            )


def check_value_expression(node, issues):
    for child in iter_annotation_nodes(node):
        if is_pep585_annotation(child):
            base_name = child.value.id
            issues.append(("PEP 585 generic", child.lineno, pep585_message(base_name)))

def find_incompatible_syntax(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError as e:
            return [("SYNTAX ERROR", e.lineno, str(e))]

    issues = []

    class Visitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            check_value_expression(node.value, issues)
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            check_annotation(node.annotation, issues)
            if node.value is not None:
                check_value_expression(node.value, issues)
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            check_function_annotations(node, issues)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            check_function_annotations(node, issues)
            self.generic_visit(node)

        def visit_Match(self, node):
            issues.append(("match-case", node.lineno, "Structural pattern matching not supported in Python 3.7"))
            self.generic_visit(node)

    Visitor().visit(tree)
    return issues


def check_function_annotations(node, issues):
    args = node.args
    all_args = args.posonlyargs + args.args + args.kwonlyargs
    if args.vararg is not None:
        all_args.append(args.vararg)
    if args.kwarg is not None:
        all_args.append(args.kwarg)
    for arg in all_args:
        check_annotation(arg.annotation, issues)
    check_annotation(node.returns, issues)

def scan_project(root_path):
    results = []
    if os.path.isfile(root_path):
        if root_path.endswith(".py") and not is_excluded_path(root_path):
            issues = find_incompatible_syntax(root_path)
            for kind, lineno, message in issues:
                results.append((root_path, lineno, kind, message))
        return results

    for dirpath, dirnames, filenames in os.walk(root_path):
        if is_excluded_path(dirpath):
            continue
        dirnames[:] = [dirname for dirname in dirnames if not is_excluded_path(os.path.join(dirpath, dirname))]
        filenames = [file for file in filenames if not file.endswith(".pyc")]
        for file in filenames:
            if file.endswith(".py"):
                filepath = os.path.join(dirpath, file)
                if is_excluded_path(filepath):
                    continue
                issues = find_incompatible_syntax(filepath)
                for kind, lineno, message in issues:
                    results.append((filepath, lineno, kind, message))
    return results

if __name__ == "__main__":
    roots = sys.argv[1:] if len(sys.argv) > 1 else ["."]
    findings = []
    for root in roots:
        findings.extend(scan_project(root))

    if not findings:
        print("✅ No Python 3.7 incompatibilities found.")
    else:
        print("❌ Found potential Python 3.7 incompatibilities:\n")
        for path, line, kind, msg in findings:
            print(f"{path}:{line} [{kind}] {msg}")
        sys.exit(1)

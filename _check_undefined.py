#!/usr/bin/env python3
"""Scan all modules for likely undefined names by checking calls against imports & local defs."""
import ast, os, glob

BUILTIN_NAMES = set(dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__)) | {
    'print', 'len', 'range', 'int', 'str', 'float', 'bool', 'list', 'dict',
    'set', 'tuple', 'type', 'super', 'isinstance', 'issubclass', 'hasattr',
    'getattr', 'setattr', 'delattr', 'callable', 'iter', 'next', 'zip',
    'map', 'filter', 'sorted', 'reversed', 'enumerate', 'any', 'all',
    'min', 'max', 'sum', 'abs', 'round', 'divmod', 'pow', 'hash', 'id',
    'input', 'open', 'repr', 'format', 'chr', 'ord', 'hex', 'oct', 'bin',
    'property', 'staticmethod', 'classmethod',
    'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
    'AttributeError', 'ImportError', 'RuntimeError', 'StopIteration',
    'FileNotFoundError', 'OSError', 'IOError', 'NotImplementedError',
    'ZeroDivisionError', 'OverflowError', 'UnicodeDecodeError',
    'True', 'False', 'None', 'NotImplemented', 'Ellipsis',
    '__name__', '__file__', '__doc__', '__all__',
    'breakpoint', 'exit', 'quit', 'copyright', 'credits', 'license',
    'object', 'bytes', 'bytearray', 'memoryview', 'complex', 'frozenset',
    'vars', 'dir', 'globals', 'locals', 'exec', 'eval', 'compile',
    'ascii', 'issubclass',
}

# These are module names that become valid names after `import X`
SAFE_MODULES = {
    'datetime', 'json', 're', 'os', 'math', 'time', 'uuid', 'base64',
    'urllib', 'pycountry', 'io', 'sys', 'traceback', 'collections',
    'functools', 'itertools', 'copy', 'hashlib', 'hmac', 'secrets',
}


def get_all_names(tree):
    """Get all names defined/assigned anywhere in the file."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                names.add(arg.arg)
            if node.args.vararg: names.add(node.args.vararg.arg)
            if node.args.kwarg: names.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            for a in node.names: names.add(a.asname or a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names: names.add(a.asname or a.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name): names.add(n.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.For):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name): names.add(n.id)
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars:
                    for n in ast.walk(item.optional_vars):
                        if isinstance(n, ast.Name): names.add(n.id)
        elif isinstance(node, ast.ExceptHandler):
            if node.name: names.add(node.name)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            for gen in node.generators:
                for n in ast.walk(gen.target):
                    if isinstance(n, ast.Name): names.add(n.id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def get_used_names(tree):
    """Get all Name nodes in Load context."""
    used = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in used:
                used[node.id] = node.lineno
    return used


def check_file(filepath):
    try:
        source = open(filepath).read()
        tree = ast.parse(source)
    except SyntaxError as e:
        return [(filepath, 0, f"SYNTAX ERROR: {e}")]

    defined = get_all_names(tree)
    used = get_used_names(tree)

    issues = []
    for name, lineno in sorted(used.items(), key=lambda x: x[1]):
        if name in defined or name in BUILTIN_NAMES or name in SAFE_MODULES:
            continue
        issues.append((filepath, lineno, name))

    return issues


files = sorted(glob.glob('**/*.py', recursive=True))
files = [f for f in files if not f.startswith('_') and 'app_original' not in f and '__pycache__' not in f]

all_issues = []
for f in files:
    all_issues.extend(check_file(f))

if all_issues:
    print(f"Found {len(all_issues)} potential undefined names:\n")
    cur = None
    for fp, ln, name in all_issues:
        if fp != cur:
            cur = fp
            print(f"\n=== {fp} ===")
        print(f"  L{ln}: {name}")
else:
    print("No issues found!")

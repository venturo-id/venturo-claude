"""Analyzer ambang struktur untuk Python (modul `ast`, presisi).

Definisi (lihat juga README, "Dukungan bahasa"):
- Panjang fungsi: baris `def`/`async def` sampai baris akhir badan, termasuk
  baris kosong dan komentar di antaranya. Decorator TIDAK dihitung (context
  structural: "dari signature sampai penutup badan").
- Kompleksitas: if/elif, for/while (termasuk async), ternary, case non-wildcard,
  tiap generator & `if` di comprehension, dan tiap `and`/`or`. Fungsi bersarang
  bernama diukur sendiri, tidak ikut fungsi induknya; lambda ikut induknya.
- Nesting: badan = level 0; if/for/while/with/try/match menambah satu level;
  `elif` tidak menambah.
- Parameter: semua parameter bernama + *args + **kwargs, tanpa self/cls pada
  method.
- Magic value: konstanta angka selain 0/1/2 di badan fungsi, kecuali assignment
  ke NAMA_KAPITAL, nilai dict, keyword argument, argumen logging/print, dan `raise`.
"""

import ast

_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
_LOG_CALLS = {"print", "debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
_ALLOWED = {0, 1, 2}


def analyze(source):
    """Kembali {lines, functions, magic, ui_component, error}."""
    lines = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as err:
        return {"lines": lines, "functions": [], "magic": [], "ui_component": False, "error": str(err)}
    functions, magic = [], []
    _collect(tree, "", None, functions, magic)
    return {"lines": lines, "functions": functions, "magic": magic, "ui_component": False, "error": None}


def _collect(node, prefix, cls, functions, magic):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            _collect(child, prefix + child.name + ".", child, functions, magic)
        elif isinstance(child, _FUNCS):
            functions.append(_measure(child, prefix + child.name, cls))
            magic.extend(_magic(child))
            _collect(child, prefix + child.name + ".", None, functions, magic)
        else:
            _collect(child, prefix, cls, functions, magic)


def _measure(fn, name, cls):
    return {
        "name": name,
        "start": fn.lineno,
        "end": fn.end_lineno,
        "lines": fn.end_lineno - fn.lineno + 1,
        "complexity": sum(_branches(n) for n in _own_nodes(fn)),
        "nesting": _nesting(fn.body, 0),
        "params": _params(fn, cls),
    }


def _own_nodes(fn):
    """Node di badan fn tanpa masuk ke fungsi/kelas bersarang bernama."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, _FUNCS + (ast.ClassDef,)):
                stack.append(child)


def _branches(node):
    if isinstance(node, (ast.If, ast.IfExp) + _LOOPS):
        return 1
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1
    if isinstance(node, ast.comprehension):
        return 1 + len(node.ifs)
    if hasattr(ast, "match_case") and isinstance(node, ast.match_case):
        wildcard = isinstance(node.pattern, ast.MatchAs) and node.pattern.pattern is None
        return 0 if wildcard else 1
    return 0


def _nesting(stmts, depth):
    deepest = depth
    for stmt in stmts:
        for block, level in _blocks(stmt, depth):
            deepest = max(deepest, level, _nesting(block, level))
    return deepest


def _blocks(stmt, depth):
    """(daftar statement, level) untuk tiap blok anak dari stmt."""
    inner = depth + 1
    if isinstance(stmt, ast.If):
        out = [(stmt.body, inner)]
        if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
            out += _blocks(stmt.orelse[0], depth)  # elif: level yang sama
        elif stmt.orelse:
            out.append((stmt.orelse, inner))
        return out
    if isinstance(stmt, _LOOPS):
        return [(stmt.body, inner), (stmt.orelse, inner)]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [(stmt.body, inner)]
    if isinstance(stmt, ast.Try) or type(stmt).__name__ == "TryStar":
        return ([(stmt.body, inner), (stmt.orelse, inner), (stmt.finalbody, inner)]
                + [(h.body, inner) for h in stmt.handlers])
    if type(stmt).__name__ == "Match":
        return [(c.body, inner) for c in stmt.cases]
    return []


def _params(fn, cls):
    a = fn.args
    names = list(a.posonlyargs) + list(a.args)
    decorators = {getattr(d, "id", getattr(d, "attr", "")) for d in fn.decorator_list}
    if cls is not None and "staticmethod" not in decorators and names and names[0].arg in ("self", "cls"):
        names = names[1:]
    return len(names) + len(a.kwonlyargs) + (1 if a.vararg else 0) + (1 if a.kwarg else 0)


def _magic(fn):
    exempt = set()
    for node in _own_nodes(fn):
        if _exempt_parent(node):
            exempt.update(id(n) for n in ast.walk(node))
    for node in _own_nodes(fn):  # nilai dict & keyword argument = data/konfigurasi bernama
        if isinstance(node, ast.Dict):
            exempt.update(id(n) for v in node.values for n in ast.walk(v))
        elif isinstance(node, ast.keyword):
            exempt.update(id(n) for n in ast.walk(node.value))
    hits = []
    for node in _own_nodes(fn):
        if (isinstance(node, ast.Constant) and type(node.value) in (int, float)
                and node.value not in _ALLOWED and id(node) not in exempt):
            hits.append({"line": node.lineno, "value": repr(node.value)})
    return hits


def _exempt_parent(node):
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return all(isinstance(t, ast.Name) and t.id.isupper() for t in targets)
    if isinstance(node, ast.Raise):
        return True
    if isinstance(node, ast.Call):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
        return name in _LOG_CALLS
    return False

"""Analyzer ambang struktur HEURISTIK untuk bahasa bergaya C.

Dipakai untuk PHP, Swift, Kotlin, Dart, Java, Vue/Svelte, dan TS/JS bila
TypeScript compiler project tidak tersedia. Semua temuannya ditandai
`heuristic: true`.

Cara kerja:
1. `sanitize`: komentar dan isi string (termasuk interpolasi `${}` / `\\()`,
   template literal, triple-quote, heredoc PHP) diganti spasi, baris baru
   dipertahankan — jadi brace/angka di dalam string atau komentar tidak terhitung.
2. Deklarasi fungsi dicari per bahasa (regex di teks yang sudah bersih), lalu
   badan `{...}` dicari dengan brace matching.
3. Metrik dihitung dari teks badan: kata kunci cabang, kedalaman brace blok,
   jumlah parameter (koma tingkat atas), literal angka.

Batas yang diketahui: regex literal JS, macro/annotation yang tidak lazim,
fungsi berbadan ekspresi (`fun f() = ...`, `=> expr;`) tidak diukur.
"""

import re

KEYWORDS = {"if", "for", "foreach", "while", "switch", "catch", "return", "function", "elseif", "else", "match",
            "when", "guard", "do", "try", "new", "await", "throw", "typeof", "sizeof", "super", "this", "assert",
            "synchronized", "with", "repeat", "case", "in", "is", "as", "yield", "delete", "void"}

_INTERP = {  # pembuka interpolasi di dalam string per bahasa → penutup
    "javascript": {"`": ("${", "}")}, "typescript": {"`": ("${", "}")}, "vue": {"`": ("${", "}")},
    "svelte": {"`": ("${", "}")},
    "kotlin": {'"': ("${", "}"), '"""': ("${", "}")},
    "dart": {'"': ("${", "}"), "'": ("${", "}"), '"""': ("${", "}"), "'''": ("${", "}")},
    "swift": {'"': ("\\(", ")"), '"""': ("\\(", ")")},
    "php": {'"': ("{$", "}")},
}
_LINE_COMMENT = {"php": ("//", "#")}
_NESTED_BLOCK_COMMENT = {"swift", "kotlin", "dart"}
_TRIPLE = {"kotlin": ('"""',), "swift": ('"""',), "dart": ('"""', "'''"), "java": ('"""',)}
_QUOTES = {"javascript": "'\"`", "typescript": "'\"`", "vue": "'\"`", "svelte": "'\"`", "swift": '"',
           "kotlin": "'\"", "dart": "'\"", "php": "'\"", "java": "'\""}


# --- sanitasi ---------------------------------------------------------------

class _Scanner:
    def __init__(self, src, lang):
        self.src, self.lang, self.out = src, lang, list(src)
        self.line_comments = _LINE_COMMENT.get(lang, ("//",))
        self.quotes = _QUOTES.get(lang, "'\"")
        self.triples = _TRIPLE.get(lang, ())
        self.interp = _INTERP.get(lang, {})

    def blank(self, a, b):
        for i in range(a, min(b, len(self.src))):
            if self.src[i] != "\n":
                self.out[i] = " "

    def code(self, i, closer=None):
        """Pindai kode mulai i; berhenti setelah `closer` pada kedalaman 0 (untuk interpolasi)."""
        depth, src, n = 0, self.src, len(self.src)
        while i < n:
            ch = src[i]
            if closer and depth == 0 and src.startswith(closer, i):
                return i + len(closer)
            if any(src.startswith(c, i) for c in self.line_comments) and not src.startswith("#[", i):
                j = src.find("\n", i)
                j = n if j < 0 else j
                self.blank(i, j)
                i = j
            elif src.startswith("/*", i):
                i = self.block_comment(i)
            elif self.lang == "php" and src.startswith("<<<", i):
                i = self.heredoc(i)
            elif any(src.startswith(t, i) for t in self.triples):
                q = next(t for t in self.triples if src.startswith(t, i))
                i = self.string(i, q)
            elif ch in self.quotes:
                i = self.string(i, ch)
            else:
                if ch in "({[":
                    depth += 1
                elif ch in ")}]":
                    depth -= 1
                i += 1
        return i

    def block_comment(self, i):
        depth, j, src = 1, i + 2, self.src
        nested = self.lang in _NESTED_BLOCK_COMMENT
        while j < len(src) and depth:
            if nested and src.startswith("/*", j):
                depth, j = depth + 1, j + 2
            elif src.startswith("*/", j):
                depth, j = depth - 1, j + 2
            else:
                j += 1
        self.blank(i, j)
        return j

    def string(self, i, quote):
        src, j = self.src, i + len(quote)
        opener = self.interp.get(quote)
        while j < len(src):
            if src[j] == "\\" and not (opener and src.startswith(opener[0], j)):
                j += 2
                continue
            if opener and src.startswith(opener[0], j):
                j = self.code(j + len(opener[0]), opener[1])
                continue
            if src.startswith(quote, j):
                j += len(quote)
                break
            if len(quote) == 1 and quote != "`" and src[j] == "\n":
                break  # string satu baris yang tidak ditutup: berhenti di akhir baris
            j += 1
        self.blank(i + len(quote), max(i + len(quote), j - len(quote)))
        return j

    def heredoc(self, i):
        m = re.match(r"<<<\s*['\"]?(\w+)['\"]?", self.src[i:])
        if not m:
            return i + 3
        end = re.compile(r"^\s*%s\b" % re.escape(m.group(1)), re.M).search(self.src, i + m.end())
        j = end.end() if end else len(self.src)
        self.blank(i, j)
        return j


def sanitize(src, lang):
    sc = _Scanner(src, lang)
    sc.code(0)
    return "".join(sc.out)


# --- deklarasi fungsi -------------------------------------------------------

_DECL = {
    "php": [re.compile(r"\bfunction\s+&?\s*([A-Za-z_]\w*)\s*\(")],
    "swift": [re.compile(r"\bfunc\s+([^\s(<]+)\s*(?:<[^>{]*>)?\s*\("),
              re.compile(r"\b(init)\s*[?!]?\s*(?:<[^>{]*>)?\s*\(")],
    "kotlin": [re.compile(r"\bfun\s+(?:<[^>{]*>\s*)?(?:[\w.<>?, ]+\.)?([A-Za-z_]\w*)\s*\("),
               re.compile(r"\b(constructor)\s*\(")],
}
_GENERIC_CALL = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*(?:<[^<>(){};]*>)?\s*\(")
_JS_ASSIGN = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*(?::\s*[^=;{}()]+)?\s*[=:]\s*(?:async\s+)?(?:function\b\s*\*?\s*[\w$]*\s*)?(?=\(|[A-Za-z_$][\w$]*\s*=>)")
_SCRIPT_LANGS = {"javascript", "typescript", "vue", "svelte"}
_GENERIC_LANGS = {"dart", "java"} | _SCRIPT_LANGS


def _match_close(text, i, open_ch, close_ch):
    """Indeks penutup yang cocok untuk text[i] == open_ch; -1 bila tidak ada."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == open_ch:
            depth += 1
        elif text[j] == close_ch:
            depth -= 1
            if depth == 0:
                return j
    return -1


def _body_start(text, i, lang):
    """Dari setelah `)` parameter, cari `{` badan; None bila badan ekspresi/deklarasi saja."""
    m = re.compile(r"\s*(?:->\s*|:\s*|throws\b|rethrows\b|async\b|\*|where\b|[\w$.<>?,\[\]&|\s]|\(\s*\))*?\{").match(text, i)
    if not m:
        return None
    gap = text[i:m.end() - 1]
    if re.search(r"[;=]|=>", gap) or (lang not in ("swift", "kotlin") and "\n\n" in gap):
        return None
    return m.end() - 1


def _split_params(params, lang):
    parts, depth, cur = [], 0, ""
    typed = lang in ("swift", "kotlin", "dart", "java", "typescript")
    for k, ch in enumerate(params):
        if ch in "([{" or (typed and ch == "<" and k and (params[k - 1].isalnum() or params[k - 1] == "_")):
            depth += 1
        elif ch in ")]}" or (typed and ch == ">" and depth and params[k - 1] != "="):
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    parts = [p.strip() for p in parts if p.strip()]
    if lang == "dart":  # parameter bernama/opsional Dart {a, b} / [a, b]: dihitung per item
        flat = []
        for p in parts:
            flat += _split_params(p[1:-1], lang) if p[:1] in "{[" and p[-1:] in "}]" else [p]
        parts = flat
    return [p for p in parts if p not in ("this",) and not p.startswith("this:")]


def _candidates(text, lang):
    """(nama, posisi awal deklarasi, posisi `(` parameter)."""
    out = []
    for rx in _DECL.get(lang, []):
        for m in rx.finditer(text):
            out.append((m.group(1), m.start(), m.end() - 1))
    if lang in _GENERIC_LANGS:
        for m in _GENERIC_CALL.finditer(text):
            if m.group(1) not in KEYWORDS:
                out.append((m.group(1), _line_start_decl(text, m.start()), m.end() - 1))
    if lang in _SCRIPT_LANGS:
        # `const X = (a) => {`, `x: async function (a) {` — parameter tanpa kurung
        # (`x => {`) dilewati; prettier selalu menambah kurung.
        for m in _JS_ASSIGN.finditer(text):
            if m.group(1) not in KEYWORDS and text[m.end():m.end() + 1] == "(":
                out.append((m.group(1), m.start(), m.end()))
    return out


def _line_start_decl(text, pos):
    """Awal deklarasi = awal baris (modifier/tipe kembalian di baris yang sama ikut)."""
    return text.rfind("\n", 0, pos) + 1


def _arrow_body(text, close, lang):
    """JS: `(...)  =>  {` atau `x => {` setelah parameter."""
    m = re.compile(r"\s*(?::\s*[^={};]+?)?\s*=>\s*\{").match(text, close + 1)
    return m.end() - 1 if m else None


def _functions(text, lang):
    found, seen = [], set()
    for name, start, paren in _candidates(text, lang):
        if paren is None or paren < 0 or text[paren] != "(":
            continue
        close = _match_close(text, paren, "(", ")")
        if close < 0:
            continue
        body = _arrow_body(text, close, lang) if lang in _SCRIPT_LANGS else None
        if body is None:
            body = _body_start(text, close + 1, lang)
        if body is None or body in seen:
            continue
        end = _match_close(text, body, "{", "}")
        if end < 0:
            continue
        seen.add(body)
        found.append({"name": name, "start": start, "body": body, "end": end,
                      "params": len(_split_params(text[paren + 1:close], lang))})
    return found


# --- metrik -----------------------------------------------------------------

_BRANCH = {
    "php": r"\b(?:if|elseif|for|foreach|while|case)\b",
    "swift": r"\b(?:if|guard|for|while|case)\b",
    "kotlin": r"\b(?:if|for|while)\b",
    "dart": r"\b(?:if|for|while|case)\b",
    "java": r"\b(?:if|for|while|case)\b",
}
_TERNARY = re.compile(r"(?<=\s)\?(?=\s)")
_NO_BLOCK_PREV = set("=(,:[?{>!&|+")


def _complexity(body, lang):
    n = len(re.findall(_BRANCH.get(lang, r"\b(?:if|for|while|case)\b"), body))
    n += body.count("&&") + body.count("||")
    if lang != "kotlin":
        n += len(_TERNARY.findall(body))
    if lang == "kotlin":
        n += _kotlin_when_branches(body)
    if lang == "swift":  # `case` di dalam `if case let` / enum pattern sudah terhitung lewat if
        n -= len(re.findall(r"\bif\s+case\b|\bguard\s+case\b", body))
    return n


def _kotlin_when_branches(body):
    n = 0
    for m in re.finditer(r"\bwhen\b[^{]*\{", body):
        end = _match_close(body, m.end() - 1, "{", "}")
        inner = body[m.end():end]
        depth = 0
        for line in inner.split("\n"):
            if depth == 0 and "->" in line and not re.match(r"\s*else\s*->", line):
                n += 1
            depth += line.count("{") - line.count("}")
    return n


def _prev_token(text, i):
    j = i - 1
    while j >= 0 and text[j] in " \t\r\n":
        j -= 1
    if j < 0:
        return ""
    if text[j - 1:j + 1] in ("->", "=>"):
        return text[j - 1:j + 1]
    m = re.search(r"[\w$]+$", text[:j + 1])
    return m.group(0) if m else text[j]


def _nesting(text, body, end, lang):
    stack, deepest = [], 0
    for i in range(body + 1, end):
        ch = text[i]
        if ch == "{":
            prev = _prev_token(text, i)
            counts = not (prev in _NO_BLOCK_PREV or prev == "return" or (prev == "->" and lang == "kotlin"))
            stack.append(counts)
            deepest = max(deepest, sum(stack))
        elif ch == "}" and stack:
            stack.pop()
    return deepest


_NUM = re.compile(r"(?<![\w$.])(?:0[xX][0-9a-fA-F_]+|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?)[fFdDlLuU]?(?![\w$.])")
_MAGIC_EXEMPT_LINE = re.compile(
    r"\b(?:const|val|let|final|static|define|var)\s+(?:[\w<>?]+\s+)?[A-Z][A-Z0-9_]*\s*[:=]|"
    r"\b(?:console|logger|log|Log|NSLog|print|println|debugPrint|printf|error_log|throw)\b|"
    r"\b\w*(?:Exception|Error)\s*\(")
_ALLOWED = {"0", "1", "2", "0.0", "1.0"}


_JSX_LINE = re.compile(r"</?[A-Za-z][\w.]*[\s/>]")


def _magic(text, body, end, line_of, script=False):
    """Literal angka di badan fungsi; nilai properti/argumen bernama, case, dan JSX dilewati."""
    hits = []
    for m in _NUM.finditer(text, body + 1, end):
        literal = m.group(0)
        if literal.rstrip("fFdDlLuU") in _ALLOWED:
            continue
        ls = text.rfind("\n", 0, m.start()) + 1
        le = text.find("\n", m.start())
        line_text = text[ls:le if le >= 0 else len(text)]
        before = text[ls:m.start()].rstrip()
        if (_MAGIC_EXEMPT_LINE.search(line_text) or before.endswith((":", "={", "[", "=>"))
                or before.endswith("case") or (script and _JSX_LINE.search(line_text))):
            continue
        hits.append({"line": line_of(m.start()), "value": literal})
    return hits


_UI_MARKERS = {
    "swift": re.compile(r"\bstruct\s+\w+\s*:\s*[^{]*\bView\b"),
    "dart": re.compile(r"\bextends\s+(?:StatelessWidget|StatefulWidget|State<)"),
    "kotlin": re.compile(r"@Composable\b"),
}


def analyze(source, lang):
    """Kembali {lines, functions, magic, ui_component, error} — skema sama dengan analyzer lain."""
    lines = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
    text = sanitize(source, lang)
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(pos):
        lo, hi = 0, len(newlines)
        while lo < hi:
            mid = (lo + hi) // 2
            if newlines[mid] < pos:
                lo = mid + 1
            else:
                hi = mid
        return lo + 1

    functions, magic = [], []
    for f in sorted(_functions(text, lang), key=lambda f: f["start"]):
        start, end_line = line_of(f["start"]), line_of(f["end"])
        body_text = text[f["body"] + 1:f["end"]]
        functions.append({"name": f["name"], "start": start, "end": end_line, "lines": end_line - start + 1,
                          "complexity": _complexity(body_text, lang),
                          "nesting": _nesting(text, f["body"], f["end"], lang), "params": f["params"]})
        magic += _magic(text, f["body"], f["end"], line_of, lang in _SCRIPT_LANGS)
    ui = bool(_UI_MARKERS.get(lang) and _UI_MARKERS[lang].search(text))
    return {"lines": lines, "functions": _dedupe(functions), "magic": magic, "ui_component": ui, "error": None}


def _dedupe(functions):
    """Satu fungsi per (nama, baris awal); deklarasi luar & dalam tetap terpisah."""
    out, seen = [], set()
    for f in functions:
        key = (f["name"], f["start"])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out

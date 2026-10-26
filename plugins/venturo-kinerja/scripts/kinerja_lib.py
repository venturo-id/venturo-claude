"""Pustaka bersama venturo-kinerja: rules, gate commit, agent-docs, doc-sync, go-thresholds.

Dipakai kinerja_status.py, render_rule.py, dan hook. Hanya stdlib python3. Semua
fungsi di sini deterministik dan lokal: tanpa jaringan, tanpa LLM.
"""

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess

import simulate_score as sim

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_DIR = os.path.join(PLUGIN_DIR, "rules")
STRUCTURAL_RULES = os.path.join(RULES_DIR, "quality-score", "structural.md")
GO_THRESHOLDS_SRC = os.path.join(PLUGIN_DIR, "scripts", "go-thresholds")
RULES_STALE_DAYS = 14

# --- placeholder context (internal/modules/review/repo/skills/skills.go) --

SEVERITY_SCOPE_WITH_MEDIUM = "Critical/High/Medium"
SEVERITY_SCOPE_WITHOUT_MEDIUM = "Critical/High"
VERDICT_MEDIUM_RULE = "- ada Medium: `Verdict: Needs work`"


def severity_penalties():
    """severityPenalties(): "critical 15, high 10, medium 5, low 2, info 0"."""
    return ", ".join("%s %d" % (sev, pen) for sev, pen in sim.SEVERITY_ORDER)


def render_placeholders(text, medium=True):
    """substituteTemplates(): render placeholder sebelum rule ditampilkan.

    medium=True = default setting kinerja (jalur tanpa resolver di Go).
    {{SECURITY_API_URL}} sengaja dibiarkan: nilainya setting server.
    """
    scope = SEVERITY_SCOPE_WITH_MEDIUM if medium else SEVERITY_SCOPE_WITHOUT_MEDIUM
    text = text.replace("{{SEVERITY_SCOPE}}", scope)
    text = text.replace("{{VERDICT_MEDIUM_RULE}}", VERDICT_MEDIUM_RULE if medium else "")
    return text.replace("{{SEVERITY_PENALTIES}}", severity_penalties())


def read_rule(slug, render=True):
    with open(os.path.join(RULES_DIR, slug + ".md"), encoding="utf-8") as fh:
        text = fh.read()
    return render_placeholders(text) if render else text


def structural_thresholds(path=STRUCTURAL_RULES):
    """Ambang dari structural.md, baris "- function_length: maks 50 — ..."."""
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^-\s+([a-z_]+):\s*maks\s+([0-9]+)\b", line)
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def rules_info(now=None):
    """Metadata snapshot rules dari rules.lock.json."""
    with open(os.path.join(RULES_DIR, "rules.lock.json"), encoding="utf-8") as fh:
        lock = json.load(fh)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    synced = _dt.datetime.fromisoformat(lock["synced_at"].replace("Z", "+00:00"))
    age = (now - synced).total_seconds() / 86400.0
    return {
        "synced_at": lock["synced_at"],
        "age_days": round(age, 1),
        "stale": age > RULES_STALE_DAYS,
        "stale_after_days": RULES_STALE_DAYS,
        "kinerja_be_commit": lock["source"].get("kinerja_be_commit"),
        "versions": {c["slug"]: c["version"] for c in lock["contexts"]},
    }


# --- gate commit (project/domain/conventional_commit.go, space_issue_gate.go)

CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([^()\r\n]+\))?!?: *\S", re.I)
SPACE_ISSUE_CODE_RE = re.compile(r"\[([A-Z][A-Z0-9]{1,5}-\d+)\]", re.I)


def is_git_generated_subject(subject):
    return subject.startswith("Merge ") or subject.startswith('Revert "')


def commit_message_problems(message):
    """Masalah pesan commit menurut gate kinerja; [] = lolos."""
    subject = message.split("\n", 1)[0].strip()
    if is_git_generated_subject(subject):
        return []
    problems = []
    if not CONVENTIONAL_COMMIT_RE.match(subject):
        problems.append("subject bukan Conventional Commit: %r (type(scope)?!?: deskripsi)" % subject)
    if not SPACE_ISSUE_CODE_RE.search(message):
        problems.append("tidak ada kode issue Space seperti [ABC-123]")
    return problems


# --- agent-docs (context agent-docs v2) -----------------------------------

AGENT_DOC_NAMES = {"CLAUDE.md", "AGENTS.md", "CLAUDE.local.md"}
ROOT_AGENT_DOCS = ["CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md", ".claude/AGENTS.md"]
AGENT_DOCS_MAX_LINES = 200
_IMPORT_RE = re.compile(r"(?<![\w`/])@((?:~|\.{1,2})?/?[\w.\-/]+\.[A-Za-z0-9]+)")
_DELEGATION_HEADING_RE = re.compile(r"^#{1,6}\s.*(delegasi|delegation|sub-?agent)", re.I | re.M)
# Lima poin wajib bagian delegasi (Cek 3) dan kata kunci yang dicari.
DELEGATION_POINTS = [
    ("pemicu", re.compile(r"pemicu|trigger|kapan", re.I)),
    ("agent tujuan", re.compile(r"agent|role", re.I)),
    ("input", re.compile(r"\binput\b|masukan", re.I)),
    ("output", re.compile(r"\boutput\b|keluaran|kembalikan", re.I)),
    ("batas read-only/boleh edit", re.compile(r"read-only|boleh edit|hanya baca|read only", re.I)),
    ("jumlah paralel maksimal", re.compile(r"paralel|parallel|bersamaan", re.I)),
]


def is_agent_doc(path):
    return os.path.basename(path) in AGENT_DOC_NAMES


def _strip_code(text):
    return re.sub(r"```.*?```", "", text, flags=re.S)


def agent_doc_imports(path, text):
    base = os.path.dirname(path)
    out = []
    for ref in _IMPORT_RE.findall(_strip_code(text)):
        target = os.path.expanduser(ref) if ref.startswith("~") else os.path.join(base, ref)
        if os.path.isfile(target):
            out.append(os.path.normpath(target))
    return out


def count_file_lines(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def agent_doc_size_problems(path):
    """Cek 1 — Ukuran: file > 200 baris, atau file + @import > 200 baris."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    own = count_file_lines(path)
    total = own + sum(count_file_lines(p) for p in agent_doc_imports(path, text))
    problems = []
    if own > AGENT_DOCS_MAX_LINES:
        problems.append("%s %d baris > %d" % (path, own, AGENT_DOCS_MAX_LINES))
    elif total > AGENT_DOCS_MAX_LINES:
        problems.append("%s + @import %d baris > %d" % (path, total, AGENT_DOCS_MAX_LINES))
    return problems


def delegation_problems(repo_root):
    """Cek 3 — gabungan file root: bagian delegasi + lima poinnya (heuristik kata kunci)."""
    texts = []
    for rel in ROOT_AGENT_DOCS:
        path = os.path.join(repo_root, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            texts.append(text)
            for imp in agent_doc_imports(path, text):
                with open(imp, encoding="utf-8", errors="replace") as fh:
                    texts.append(fh.read())
    section = _delegation_section("\n".join(texts))
    if section is None:
        return ["bagian delegasi sub agent tidak ada"]
    missing = [name for name, rx in DELEGATION_POINTS if not rx.search(section)]
    return ["bagian delegasi tidak menyebut: " + ", ".join(missing)] if missing else []


def _delegation_section(text):
    m = _DELEGATION_HEADING_RE.search(text)
    if not m:
        return None
    level = len(text[m.start():].split(" ", 1)[0])
    rest = text[m.end():]
    nxt = re.search(r"^#{1,%d}\s" % level, rest, re.M)
    return rest[: nxt.start()] if nxt else rest


# --- file yang tidak dinilai sebagai kode -----------------------------------

LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock", "go.sum", "Cargo.lock",
             "pubspec.lock", "Podfile.lock", "Package.resolved", "poetry.lock", "Pipfile.lock", "uv.lock",
             "gradle.lockfile", "bun.lockb"}
TEST_PATH_RE = re.compile(
    r"(_test\.(go|dart|py)$|(^|/)test_[^/]*\.py$|\.(test|spec)\.[cm]?[jt]sx?$|(^|/)(__tests__|tests?|spec)/"
    r"|Tests?\.(swift|kt|java)$|Test\.php$)")


def is_test_path(path):
    return bool(TEST_PATH_RE.search(path.replace(os.sep, "/")))


# --- deteksi stack (manifest) ----------------------------------------------

_SKIP_DIRS = {"node_modules", "vendor", "dist", "build", ".next", "out", "coverage", "Pods", "DerivedData",
              ".git", ".dart_tool", ".gradle", "__pycache__", ".venv", "venv", "docs"}
_MONOREPO_PARENTS = {"apps", "packages", "services", "libs", "backend", "frontend", "mobile", "web", "api"}
_NODE_BACKENDS = ("express", "@nestjs/core", "fastify", "koa", "@hapi/hapi", "hono")
_PHP_FRAMEWORKS = [("laravel/framework", "laravel"), ("codeigniter4/framework", "codeigniter"),
                   ("codeigniter/framework", "codeigniter"), ("slim/slim", "slim")]
_PY_MANIFESTS = ("pyproject.toml", "setup.py", "setup.cfg", "Pipfile")


def _read_text(path, limit=200000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def _js_stack(d):
    try:
        pkg = json.loads(_read_text(os.path.join(d, "package.json")))
    except ValueError:
        return None
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(pkg.get(key) or {})
    lang = "typescript" if "typescript" in deps or os.path.isfile(os.path.join(d, "tsconfig.json")) else "javascript"
    if "react-native" in deps:
        return {"id": "react-native", "language": lang, "framework": "react-native", "rules": ["react-native"]}
    if "next" in deps:
        return {"id": "react", "language": lang, "framework": "nextjs", "rules": ["react"]}
    if "react" in deps:
        return {"id": "react", "language": lang, "framework": "react", "rules": ["react"]}
    fw = next((d_ for d_ in _NODE_BACKENDS if d_ in deps), None)
    return {"id": "node", "language": lang, "framework": fw, "rules": ["node"]}


def _php_stack(d):
    text = _read_text(os.path.join(d, "composer.json"))
    fw = next((name for pkg, name in _PHP_FRAMEWORKS if '"%s"' % pkg in text), None)
    return {"id": "php", "language": "php", "framework": fw, "rules": ["php"] + (["php/" + fw] if fw else [])}


def _python_stack(d):
    names = [n for n in _PY_MANIFESTS if os.path.isfile(os.path.join(d, n))]
    names += sorted(n for n in os.listdir(d) if re.match(r"requirements.*\.txt$", n))
    if not names:
        return None
    text = " ".join(_read_text(os.path.join(d, n)) for n in names).lower()
    fw = next((f for f in ("fastapi", "django", "flask") if f in text), None)
    return {"id": "python", "language": "python", "framework": fw, "rules": [], "manifest": names[0]}


def _gradle_stack(d):
    names = [n for n in ("build.gradle.kts", "build.gradle", "settings.gradle.kts", "settings.gradle")
             if os.path.isfile(os.path.join(d, n))]
    if not names:
        return None
    text = " ".join(_read_text(os.path.join(d, n)) for n in names)
    if "kotlin" in text or names[0].endswith(".kts"):
        return {"id": "kotlin", "language": "kotlin", "framework": "android" if "android" in text else None,
                "rules": ["kotlin"], "manifest": names[0]}
    return {"id": "java", "language": "java", "framework": None, "rules": [], "manifest": names[0]}


def _stacks_in(d):
    out = []
    has = lambda name: os.path.isfile(os.path.join(d, name))  # noqa: E731
    if has("go.mod"):
        out.append({"id": "go", "language": "go", "framework": None, "rules": ["golang"], "manifest": "go.mod"})
    if has("package.json"):
        st = _js_stack(d)
        if st:
            out.append(dict(st, manifest="package.json"))
    if has("composer.json"):
        out.append(dict(_php_stack(d), manifest="composer.json"))
    for st in (_python_stack(d), _gradle_stack(d)):
        if st:
            out.append(st)
    entries = os.listdir(d)
    apple = [n for n in entries if n.endswith((".xcodeproj", ".xcworkspace"))] + \
        [n for n in ("Package.swift", "Podfile") if n in entries]
    if apple:
        out.append({"id": "ios-swift", "language": "swift", "framework": None, "rules": ["ios-swift"],
                    "manifest": apple[0]})
    if has("pubspec.yaml"):
        out.append({"id": "flutter", "language": "dart", "framework": "flutter", "rules": ["flutter"],
                    "manifest": "pubspec.yaml"})
    return out


def _candidate_dirs(root):
    yield root
    try:
        children = sorted(e for e in os.listdir(root) if not e.startswith(".") and e not in _SKIP_DIRS)
    except OSError:
        return
    for name in children:
        sub = os.path.join(root, name)
        if not os.path.isdir(sub):
            continue
        yield sub
        if name in _MONOREPO_PARENTS:
            for inner in sorted(os.listdir(sub)):
                if not inner.startswith(".") and os.path.isdir(os.path.join(sub, inner)):
                    yield os.path.join(sub, inner)


def detect_stacks(root):
    """Stack dari manifest di root, subfolder langsung, dan apps/*, packages/* (monorepo sederhana).

    Kembali list {id, language, framework, rules, manifest, path} — [] bila tidak dikenali.
    """
    out, seen = [], set()
    for d in _candidate_dirs(root):
        rel = os.path.relpath(d, root).replace(os.sep, "/")
        for st in _stacks_in(d):
            key = (st["id"], rel)
            if key not in seen:
                seen.add(key)
                out.append(dict(st, path=rel))
    return out


def repo_root(path, fallback=None):
    """Akar repo git; bukan repo git → fallback (mis. cwd sesi) atau direktori path."""
    start = path if os.path.isdir(path) else os.path.dirname(path)
    return find_up(start, ".git") or (os.path.abspath(fallback) if fallback else os.path.abspath(start))


def supported_repo(path, fallback=None):
    """Stack yang dikenali untuk repo yang memuat path; [] = hook harus diam.

    Selain detect_stacks(akar repo), manifest dicari naik dari folder path sampai
    akar repo — supaya proyek bersarang lebih dalam dari monorepo sederhana tetap dikenali.
    """
    root = repo_root(path, fallback)
    stacks = detect_stacks(root)
    cur = os.path.abspath(path if os.path.isdir(path) else os.path.dirname(path))
    while not stacks and cur.startswith(root):
        stacks = [dict(st, path=os.path.relpath(cur, root)) for st in _stacks_in(cur)]
        if cur == root:
            break
        cur = os.path.dirname(cur)
    return stacks


# --- doc-sync heuristik ------------------------------------------------------
# Go: selaras scripts/check-doc-sync.sh skeleton-go. Stack lain: berkas permukaan
# API/kontrak/skema berubah → dokumen di `docs/` (atau kontrak OpenAPI) harus ikut.

_MIGRATION_RE = re.compile(r"^internal/database/migrations/([^/]+)/")
_MODULE_API_RE = re.compile(r"^internal/modules/([^/]+)/.*/(handler|dto)/")
_OTHER_API_RE = re.compile(r"(^internal/router/|(^|/)(handler|dto)/|\.proto$|(^|/)openapi\.ya?ml$)")
_DOC_RULES = {  # stack id → pola berkas permukaan API (doc wajib: docs/)
    "react": [r"(^|/)app/(.+/)?route\.[cm]?[jt]sx?$", r"(^|/)pages/api/",
              r"(^|/)src/(.+/)?api/[^/]+\.[cm]?[jt]sx?$", r"(^|/)src/(.+/)?services?/[^/]+\.[cm]?[jt]sx?$"],
    "node": [r"(^|/)(routes?|controllers?|api)/.+\.[cm]?[jt]s$", r"\.(controller|routes?|router|dto)\.[cm]?[jt]s$",
             r"(^|/)(migrations|prisma)/"],
    "php": [r"(^|/)routes/(api|web)\.php$", r"(^|/)app/Http/(Controllers|Requests|Resources)/",
            r"(^|/)database/migrations/", r"(^|/)app/Controllers/", r"(^|/)application/controllers/",
            r"(^|/)app/Config/Routes\.php$", r"(^|/)(app/)?routes\.php$", r"(^|/)src/(Action|Controller)s?/"],
    "python": [r"(^|/)(routers?|api|endpoints|views)(/|\.py$)", r"(^|/)(urls|serializers|schemas)\.py$",
               r"(^|/)(alembic/versions|migrations)/.+\.py$"],
}
_DOC_LIKE = re.compile(r"(^|/)docs/|(^|/)(openapi|swagger)[^/]*\.(ya?ml|json)$|(^|/)api-contract/")


def doc_sync_check(paths, stacks=None):
    """Kode API/route/dto/migration berubah tanpa dokumen pasangannya.

    stacks: daftar id stack (None = semua aturan). Kembali:
    {applicable, updated, api_files, missing, changelog_updated}.
    """
    changed = set(paths)
    missing, api_files = [], []
    for path in sorted(changed):
        if is_test_path(path) or path.endswith(".md"):
            continue
        need = _required_doc(path, stacks)
        if need is None:
            continue
        api_files.append(path)
        if not _doc_present(need, changed):
            missing.append("%s -> %s" % (path, need))
    return {
        "applicable": bool(api_files),
        "updated": bool(api_files) and not missing,
        "api_files": api_files,
        "missing": missing,
        "changelog_updated": any(os.path.basename(p) == "CHANGELOG.md" for p in changed),
    }


def _doc_present(need, changed):
    if need == "docs/":
        return any(_DOC_LIKE.search(p) for p in changed)
    return any(p == need or p.startswith(need) for p in changed)


def _required_doc(path, stacks):
    if stacks is None or "go" in stacks:
        m = _MIGRATION_RE.match(path)
        if m:
            return "docs/erd/%s.mmd" % m.group(1)
        m = _MODULE_API_RE.match(path)
        if m:
            return "docs/api-contract/%s/" % m.group(1)
        if _OTHER_API_RE.search(path) and path.endswith((".go", ".proto", ".yaml", ".yml")):
            return "docs/api-contract/"
    for sid, patterns in _DOC_RULES.items():
        if (stacks is None or sid in stacks) and any(re.search(p, path) for p in patterns):
            return "docs/"
    return None


# --- repo & go-thresholds -------------------------------------------------

def find_up(start, name):
    """Direktori terdekat ke atas dari start yang memuat name, atau None."""
    cur = os.path.abspath(start if os.path.isdir(start) else os.path.dirname(start))
    while True:
        if os.path.exists(os.path.join(cur, name)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def is_go_repo(path):
    return find_up(path, "go.mod") is not None


def _source_digest():
    h = hashlib.sha256()
    for name in sorted(os.listdir(GO_THRESHOLDS_SRC)):
        if name.endswith(".go") and not name.endswith("_test.go") or name == "go.mod":
            with open(os.path.join(GO_THRESHOLDS_SRC, name), "rb") as fh:
                h.update(name.encode() + b"\0" + fh.read())
    return h.hexdigest()[:12]


def _cache_dir():
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "venturo-kinerja")
    return os.path.join(base, "bin")


def go_thresholds_binary():
    """Path binary go-thresholds (dibangun sekali per versi sumber), atau None tanpa Go."""
    go = shutil.which("go")
    if go is None:
        return None
    target = os.path.join(_cache_dir(), "go-thresholds-" + _source_digest())
    if os.path.isfile(target):
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp%d" % os.getpid()
    env = dict(os.environ, GOWORK="off", GOFLAGS="", CGO_ENABLED="0")
    try:
        subprocess.run([go, "build", "-o", tmp, "."], cwd=GO_THRESHOLDS_SRC, env=env,
                       capture_output=True, timeout=120, check=True)
        os.replace(tmp, target)
    except (OSError, subprocess.SubprocessError):
        return None
    return target


def run_go_thresholds(targets, rules=STRUCTURAL_RULES, all_functions=False):
    """targets: [{"path": abs, "ranges": [[a,b]]}]. Kembali dict output, atau None."""
    binary = go_thresholds_binary()
    if binary is None or not targets:
        return None
    cmd = [binary, "-rules", rules, "-stdin"] + (["-all"] if all_functions else [])
    try:
        proc = subprocess.run(cmd, input=json.dumps({"files": targets}), capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)

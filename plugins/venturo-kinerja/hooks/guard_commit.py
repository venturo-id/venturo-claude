"""PreToolUse · Bash — tolak `git commit` yang pesannya pasti ditolak gate kinerja.

Regex = project/domain/conventional_commit.go + space_issue_gate.go. Hanya
pesan dari -m/--message (termasuk heredoc `-m "$(cat <<'EOF' ... EOF)"`) yang
dinilai. -F, -C, --amend tanpa -m, editor, atau pesan berisi substitusi shell
dilewati: hook tidak menebak pesan yang tidak bisa dipastikan.
"""

import re
import shlex

from _common import block, guarded, lib, project_dir, supported

GIT_COMMIT_RE = re.compile(r"(?:^|[;&|(]|\s)git((?:\s+-[Cc]\s+\S+)*)\s+commit\b")
HEREDOC_RE = re.compile(r"""-m\s+"\$\(cat\s+<<-?\s*['"]?(\w+)['"]?\s*\n(.*?)\n\s*\1\s*\n?\s*\)\"""", re.S)
UNSURE_FLAGS = {"-F", "--file", "-C", "--reuse-message", "-c", "--reedit-message", "--fixup", "--squash",
                "--no-edit", "-t", "--template"}
SHELL_OPS = {"&&", "||", ";", "|", ">", ">>", "<"}


def _message_args(tokens):
    """Nilai -m/--message, atau None bila pesan tidak bisa dipastikan."""
    msgs, i = [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in SHELL_OPS:
            break
        flag = tok.split("=", 1)[0]
        if flag in UNSURE_FLAGS or any(tok.startswith(f) for f in ("--fixup=", "--squash=", "-F")):
            return None
        if tok.startswith("--message="):
            msgs.append(tok.split("=", 1)[1])
        elif tok == "--message" or re.match(r"^-[a-zA-Z]*m", tok):
            # -m, -am, -sm: nilai menempel ("-mpesan") atau token berikutnya
            value = "" if tok == "--message" else tok[tok.index("m", 1) + 1:]
            if value == "":
                if i + 1 >= len(tokens):
                    return None
                i += 1
                value = tokens[i]
            msgs.append(value)
        i += 1
    return msgs or None


def commit_message(command):
    m = GIT_COMMIT_RE.search(command)
    if not m:
        return None
    rest = command[m.end():]
    here = HEREDOC_RE.search(rest)
    if here:
        return here.group(2)
    try:
        tokens = shlex.split(rest, posix=True)
    except ValueError:
        return None
    msgs = _message_args(tokens)
    if msgs is None or any("$(" in x or "`" in x or re.search(r"\$\w", x) for x in msgs):
        return None
    return "\n\n".join(msgs)


def repo_dir(command, cwd):
    m = GIT_COMMIT_RE.search(command)
    opts = shlex.split(m.group(1)) if m and m.group(1) else []
    for i, tok in enumerate(opts[:-1]):
        if tok == "-C":
            return opts[i + 1] if opts[i + 1].startswith("/") else cwd + "/" + opts[i + 1]
    return cwd


def main(event):
    command = (event.get("tool_input") or {}).get("command") or ""
    if "commit" not in command or not supported(repo_dir(command, project_dir(event)), event):
        return
    message = commit_message(command)
    if message is None:
        return
    problems = lib.commit_message_problems(message)
    if problems:
        block("venturo-kinerja: commit ini akan membuat PR tidak dinilai (gate kinerja):\n"
              + "\n".join("- " + p for p in problems)
              + "\nFormat: type(scope): deskripsi [KODE-123]; type = build|chore|ci|docs|feat|fix|perf|"
                "refactor|revert|style|test. Minta kode issue Space ke engineer bila belum tahu.")


if __name__ == "__main__":
    guarded(main)

"""The agent's tools, confined to one task workspace.

Tools: run_command, read_file, edit_file, write_file, get_status, submit_patch. Budgets and output caps
keep a small model's context small. run_command runs inside bubblewrap when it is available: only system
directories and the Python environment are mounted (read-only), the workspace is the only writable
place, and there is no network. Without bubblewrap
(for example on a locked-down CI runner) only an allowlist of read and test commands may run, without a
shell.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .repo import git

OUTPUT_CAP = 1500  # characters of tool output shown to the model
READ_LINES_CAP = 80
COMMAND_TIMEOUT = 60
ALLOWED = {"ls", "cat", "head", "tail", "grep", "find", "wc", "sed", "git", "python", "python3", "pytest"}
META = re.compile(r"[;&|<>`$]")


def bwrap_available() -> bool:
    if not shutil.which("bwrap"):
        return False
    r = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--unshare-all", "--die-with-parent", "true"],
                       capture_output=True)
    return r.returncode == 0


BWRAP = bwrap_available()
SYSTEM_DIRS = ("/usr", "/bin", "/lib", "/lib64", "/sbin", "/etc")


def ro_binds() -> list[str]:
    """Read-only mounts: system directories and the Python environment, nothing else from the host
    (no home directory, no other repositories, no credentials)."""
    dirs = [d for d in SYSTEM_DIRS if Path(d).exists()]
    for prefix in {sys.prefix, sys.base_prefix}:
        if not any(prefix == d or prefix.startswith(d + "/") for d in dirs):
            dirs.append(prefix)
    out = []
    for d in dirs:
        out += ["--ro-bind", d, d] if not Path(d).is_symlink() else ["--symlink", str(Path(d).readlink()), d]
    return out


def cap(text: str, limit: int = OUTPUT_CAP) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 40] + f"\n... [truncated {len(text) - limit + 40} chars]"


def check_allowlisted(command: str) -> str | None:
    """Reason to refuse a command in allowlist mode, or None if it may run."""
    if META.search(command):
        return "shell operators are not allowed"
    try:
        argv = shlex.split(command)
    except ValueError as e:
        return f"cannot parse command: {e}"
    if not argv or argv[0] not in ALLOWED:
        return f"command not allowed: {argv[0] if argv else ''}"
    if argv[0] in ("python", "python3") and argv[1:3] != ["-m", "pytest"]:
        return "python may only run 'python -m pytest'"
    if argv[0] == "git" and (len(argv) < 2 or argv[1] not in ("diff", "status", "log", "show", "grep")):
        return "only read-only git commands are allowed"
    if argv[0] == "sed" and "-i" in " ".join(argv):
        return "sed -i is not allowed; use edit_file"
    return None


@dataclass
class Workspace:
    root: Path
    max_tool_calls: int = 15
    calls: int = 0
    submitted: bool = False
    log: list[dict] = field(default_factory=list)

    # -- helpers ---------------------------------------------------------------------------------
    def _path(self, rel: str) -> Path:
        rel = rel.strip().removeprefix("/workspace/").lstrip("/") if rel else ""
        p = (self.root / rel).resolve()
        if p != self.root.resolve() and self.root.resolve() not in p.parents:
            raise PermissionError(f"path outside the workspace: {rel}")
        return p

    def call(self, tool: str, args: dict) -> str:
        budgeted = tool not in ("get_status", "submit_patch")
        if budgeted and self.calls >= self.max_tool_calls:
            out = {"error": "tool budget used up; call submit_patch"}
        else:
            self.calls += budgeted
            fn = getattr(self, f"t_{tool}", None)
            try:
                out = fn(**args) if fn else {"error": f"unknown tool {tool!r}"}
            except TypeError as e:
                out = {"error": f"bad arguments: {e}"}
            except (OSError, PermissionError, ValueError) as e:
                out = {"error": str(e)}
        text = json.dumps(out)
        self.log.append({"tool": tool, "args": args, "ok": "error" not in out, "chars": len(text)})
        return text

    # -- tools -----------------------------------------------------------------------------------
    def t_run_command(self, command: str) -> dict:
        env = {"PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": ".", "LANG": "C.UTF-8"}
        if BWRAP:
            argv = ["bwrap", *ro_binds(), "--tmpfs", "/tmp", "--bind", str(self.root), "/tmp/workspace",
                    "--dev", "/dev", "--proc", "/proc", "--unshare-all", "--die-with-parent",
                    "--chdir", "/tmp/workspace", "bash", "-c", command]
        else:
            reason = check_allowlisted(command)
            if reason:
                return {"error": reason}
            argv = shlex.split(command)
            if argv[0] == "pytest":
                argv = [sys.executable, "-m", "pytest", *argv[1:]]
            elif argv[0] in ("python", "python3"):
                argv = [sys.executable, *argv[1:]]
        try:
            r = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, timeout=COMMAND_TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            return {"error": f"timed out after {COMMAND_TIMEOUT}s"}
        return {"exit_code": r.returncode, "output": cap(r.stdout + r.stderr)}

    def t_read_file(self, filepath: str, start_line: int | None = None, end_line: int | None = None) -> dict:
        lines = self._path(filepath).read_text().splitlines()
        s = max(1, int(start_line or 1))
        e = min(len(lines), int(end_line or len(lines)), s + READ_LINES_CAP - 1)
        body = "\n".join(f"{i}: {lines[i - 1]}" for i in range(s, e + 1))
        return {"content": cap(body), "lines": f"{s}-{e} of {len(lines)}", "is_truncated": e < len(lines)}

    def t_edit_file(self, filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> dict:
        p = self._path(filepath)
        src = p.read_text()
        n = src.count(old_string) if old_string else 0
        if n == 0:
            return {"error": "old_string not found; copy it exactly from read_file output (without line numbers)"}
        if n > 1 and not allow_multiple:
            return {"error": f"old_string matches {n} places; add more context"}
        p.write_text(src.replace(old_string, new_string))
        return {"replaced": n}

    def t_write_file(self, filepath: str, content: str) -> dict:
        p = self._path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"written": len(content)}

    def t_get_status(self) -> dict:
        return {"tool_calls_used": self.calls, "tool_calls_left": self.max_tool_calls - self.calls,
                "files_changed": self.diff().count("\n+++ ")}

    def t_submit_patch(self) -> dict:
        self.submitted = True
        return {"submitted": True, "patch_lines": len(self.diff().splitlines())}

    def diff(self) -> str:
        git(self.root, "add", "-N", ".")
        return git(self.root, "diff", "HEAD").stdout

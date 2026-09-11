"""
Instant GDScript checks, no subprocess.

Runs before Godot's own parser. Every rule here fires on a mistake actually
observed coming out of the model, and each costs microseconds instead of the
~1.5s a `godot --check-only` process takes. Catching a mixed-indentation file
here saves a full engine round trip.

This never replaces Godot's parser — it runs in front of it.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

# Godot 3 idioms the model still reaches for. Godot 4 rejects all of them.
_GODOT3_PATTERNS = [
    (re.compile(r"\bmove_and_slide\s*\([^)]+\)"),
     "move_and_slide() takes NO arguments in Godot 4. Set `velocity` first, then call move_and_slide()."),
    (re.compile(r"\bexport\s+var\b"),
     "`export var` is Godot 3. Use `@export var` in Godot 4."),
    (re.compile(r"\bonready\s+var\b"),
     "`onready var` is Godot 3. Use `@onready var` in Godot 4."),
    (re.compile(r"\byield\s*\("),
     "`yield()` is Godot 3. Use `await` in Godot 4."),
    (re.compile(r"\bKinematicBody2D\b"),
     "KinematicBody2D is Godot 3. Use CharacterBody2D in Godot 4."),
    (re.compile(r"\.instance\s*\(\s*\)"),
     "`.instance()` is Godot 3. Use `.instantiate()` in Godot 4."),
    (re.compile(r"\bget_node\s*\(\s*['\"]\.\./"),
     "Relative '../' node paths are fragile. Use an @export or absolute path."),
    (re.compile(r"\bOS\.get_ticks_msec\b"),
     "Use Time.get_ticks_msec() in Godot 4."),
    (re.compile(r"\bemit_signal\s*\(\s*['\"]"),
     "Prefer `signal_name.emit(...)` in Godot 4 (emit_signal still works but is legacy)."),
    (re.compile(r"\bconnect\s*\(\s*['\"][a-z_]+['\"]\s*,\s*self\s*,"),
     "Godot 3 connect() signature. Use `node.signal_name.connect(callable)` in Godot 4."),
]

_BUILTIN_ACTIONS = {
    "ui_left", "ui_right", "ui_up", "ui_down", "ui_accept", "ui_cancel",
    "ui_select", "ui_focus_next", "ui_focus_prev", "ui_home", "ui_end",
    "ui_page_up", "ui_page_down", "ui_text_submit",
}
_ACTION_CALL = re.compile(r"Input\.(?:is_action_[a-z_]+|get_axis|get_vector)\s*\(\s*\"([^\"]+)\"")


@dataclass
class LintIssue:
    line: Optional[int]
    message: str

    def as_prompt_line(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


def lint_gdscript(source: str, declared_actions: Optional[List[str]] = None) -> List[LintIssue]:
    issues: List[LintIssue] = []

    if not source or not source.strip():
        return [LintIssue(None, "File is empty.")]

    if "```" in source:
        issues.append(LintIssue(None, "Markdown code fences (```) are in the file. Output raw code only."))

    lines = source.split("\n")

    # --- extends must be the first meaningful line ---
    first = next((l for l in lines if l.strip() and not l.strip().startswith("#")), "")
    if not first.strip().startswith(("extends", "class_name", "@tool")):
        issues.append(LintIssue(1, "First statement must be `extends <NodeType>`."))

    # --- indentation: Godot rejects a file that mixes tabs and spaces ---
    uses_tab = uses_space = False
    for n, line in enumerate(lines, 1):
        stripped = line.lstrip(" \t")
        if not stripped or stripped.startswith("#"):
            continue
        indent = line[: len(line) - len(stripped)]
        if not indent:
            continue
        if "\t" in indent and " " in indent:
            issues.append(LintIssue(n, "Indentation mixes tabs and spaces on the same line. Use tabs only."))
        elif "\t" in indent:
            uses_tab = True
        elif " " in indent:
            uses_space = True
    if uses_tab and uses_space:
        issues.append(LintIssue(None, "File mixes tab-indented and space-indented lines. Use tabs throughout."))

    # --- balance, ignoring strings and comments ---
    cleaned = _strip_strings_and_comments(source)
    for open_c, close_c, name in (("(", ")", "parentheses"), ("[", "]", "brackets"), ("{", "}", "braces")):
        diff = cleaned.count(open_c) - cleaned.count(close_c)
        if diff:
            more = "opening" if diff > 0 else "closing"
            issues.append(LintIssue(None, f"Unbalanced {name}: {abs(diff)} extra {more}."))

    # --- Godot 3 API ---
    for pattern, message in _GODOT3_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            issues.append(LintIssue(cleaned[: match.start()].count("\n") + 1, message))

    # --- input actions must exist ---
    allowed = _BUILTIN_ACTIONS | set(declared_actions or [])
    for match in _ACTION_CALL.finditer(cleaned):
        action = match.group(1)
        if action not in allowed:
            issues.append(LintIssue(
                cleaned[: match.start()].count("\n") + 1,
                f"Input action \"{action}\" is not defined. Use a built-in "
                f"(ui_left, ui_right, ui_up, ui_down, ui_accept) or it will never fire.",
            ))

    # --- a body-less block is a parse error ---
    for n, line in enumerate(lines, 1):
        if re.match(r"^\s*(func |if |elif |else|for |while |match )", line) and line.rstrip().endswith(":"):
            following = next(
                (l for l in lines[n:] if l.strip() and not l.strip().startswith("#")), None
            )
            if following is None:
                issues.append(LintIssue(n, "Block opens with ':' but has no body."))
                break
            cur_indent = len(line) - len(line.lstrip(" \t"))
            next_indent = len(following) - len(following.lstrip(" \t"))
            if next_indent <= cur_indent:
                issues.append(LintIssue(n, "Block opens with ':' but the next line is not indented."))

    return issues


def _strip_strings_and_comments(source: str) -> str:
    """Blank out string literals and comments so counting is not fooled by them."""
    out = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        if ch == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            triple = source[i:i + 3] in ("'''", '"""')
            marker = quote * 3 if triple else quote
            i += len(marker)
            while i < n and source[i:i + len(marker)] != marker:
                if source[i] == "\\":
                    i += 1
                i += 1
            i += len(marker)
            out.append('""')
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def lint_tscn(source: str) -> List[LintIssue]:
    """
    Cheap structural checks on a scene file. Deliberately narrow: Godot
    tolerates a wrong load_steps entirely, so only things that are certainly
    wrong are reported here.
    """
    issues: List[LintIssue] = []
    if not source or not source.strip():
        return [LintIssue(None, "File is empty.")]
    if "```" in source:
        issues.append(LintIssue(None, "Markdown code fences (```) are in the file. Output raw code only."))

    if not source.lstrip().startswith("[gd_scene"):
        issues.append(LintIssue(1, "A .tscn must start with a [gd_scene ...] header."))
    elif "format=3" not in source.split("\n")[0]:
        issues.append(LintIssue(1, "Scene header must declare format=3 for Godot 4."))

    nodes = re.findall(r"^\[node name=\"([^\"]+)\"(?:[^\]]*?)\]", source, re.M)
    if not nodes:
        issues.append(LintIssue(None, "No [node ...] entries — the scene has no content."))

    # Every referenced id must have been declared.
    declared = set(re.findall(r"^\[(?:ext|sub)_resource[^\]]*id=\"([^\"]+)\"", source, re.M))
    for ref in set(re.findall(r"(?:ExtResource|SubResource)\(\"([^\"]+)\"\)", source)):
        if ref not in declared:
            issues.append(LintIssue(None, f"Resource id \"{ref}\" is used but never declared."))

    # Parent paths must name an earlier node.
    seen: set = set()
    for match in re.finditer(r"^\[node name=\"([^\"]+)\"[^\]]*?(?:parent=\"([^\"]+)\")?\]", source, re.M):
        name, parent = match.group(1), match.group(2)
        line_no = source[: match.start()].count("\n") + 1
        if parent is None:
            seen.add(name)
            continue
        if parent != ".":
            root = parent.split("/")[0]
            if root not in seen and parent not in seen:
                issues.append(LintIssue(
                    line_no,
                    f"Node \"{name}\" declares parent=\"{parent}\" but no such node was "
                    f"defined earlier. It will be silently detached.",
                ))
        seen.add(f"{parent}/{name}" if parent != "." else name)

    return issues

"""v2 — supports both 'single' and "double" quoted Python strings."""
import re, sys
from pathlib import Path

PATH = Path("api/venue_aliases.py")
src = PATH.read_text()

# A quoted string: either '…' (no unescaped ') or "…" (no unescaped ").
STR = r'''(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")'''

VAL = re.compile(
    r"(\):\s*\()"                # `): (`
    rf"({STR})"                  # canonical_venue quoted
    r"(,\s*)"
    rf"({STR})"                  # canonical_city quoted
    r"(,\s*)"
    rf"({STR})"                  # country quoted
    r"(\),)"
)

def unquote(q: str) -> tuple[str, str]:
    """Return (contents, quote_char)."""
    ch = q[0]
    return (q[1:-1].replace(f"\\{ch}", ch), ch)

def quote(contents: str, prefer: str) -> str:
    """Quote `contents` preferring `prefer` char; swap if contents has it."""
    if prefer == "'" and "'" in contents and '"' not in contents:
        return f'"{contents}"'
    if prefer == '"' and '"' in contents and "'" not in contents:
        return f"'{contents}'"
    # Fallback: escape the preferred char inside it
    if prefer in contents:
        return f'{prefer}{contents.replace(prefer, chr(92) + prefer)}{prefer}'
    return f"{prefer}{contents}{prefer}"

changed = 0
scanned = 0

def rewrite(m):
    global changed, scanned
    pre, q_v, sep1, q_c, sep2, q_co, post = m.groups()
    scanned += 1
    can_v, v_quote = unquote(q_v)
    can_c, _ = unquote(q_c)
    suffix = f", {can_c}"
    if can_v.endswith(suffix) and len(can_v) > len(suffix):
        new_v = can_v[: -len(suffix)]
        changed += 1
        return f"{pre}{quote(new_v, v_quote)}{sep1}{q_c}{sep2}{q_co}{post}"
    return m.group(0)

new_src = VAL.sub(rewrite, src)

print(f"value-tuple lines scanned: {scanned}")
print(f"stripped:                  {changed}")

if "--apply" in sys.argv:
    PATH.write_text(new_src)
    print("→ wrote", PATH)

#!/usr/bin/env python3
"""Fail the build on the docs rules a script can check.

Every rule here is one that already reached the live site once. A rule a
script can check should never be left to a reviewer to notice.

    python3 scripts/check_docs_rules.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES: list[str] = []

# Words that stay capitalised inside a sentence-case title.
PROPER = {"FormBharo", "Claude", "ARMMAN", "PDF", "API", "URL", "JSON", "S3", "AI"}


def fail(where, line, rule, detail):
    FAILURES.append(f"{where}:{line}\n    [{rule}] {detail}" if line else f"{where}\n    [{rule}] {detail}")


# .claude holds Claude Code's worktrees, each a second copy of every page here.
# Scanning those reports the same page many times over and calls each copy
# missing from the nav.
IGNORED_DIRS = {".git", ".claude"}


def pages():
    return sorted(
        p for p in ROOT.rglob("*.mdx") if not IGNORED_DIRS & set(p.parts)
    )


def rel(p):
    return str(p.relative_to(ROOT))


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"')
    return out


def body(text):
    return re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)


def code_fences(text):
    """Yield (first_line_number, fence_body) for every fenced block."""
    inside, start, buf = False, 0, []
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            if inside:
                yield start, "\n".join(buf)
                inside, buf = False, []
            else:
                inside, start = True, i
            continue
        if inside:
            buf.append(line)


def strip_code(text):
    return re.sub(r"```.*?```", "", text, flags=re.S)


# --- checks -------------------------------------------------------------------


def check_no_em_dashes(p, text):
    for i, line in enumerate(text.splitlines(), 1):
        if "—" in line:
            fail(rel(p), i, "em-dash", "use a comma, a colon, or two sentences")


def check_no_snippet_var_in_code(p, text):
    """MDX does not substitute a snippet variable inside a fence, so the reader
    copies the literal placeholder and the command fails.

    Only snippet imports count. A Python f-string or JS template literal using a
    variable defined in the same block is fine.
    """
    imported = set()
    for m in re.finditer(r'import\s*\{([^}]*)\}\s*from\s*"/snippets/', text):
        imported.update(n.strip() for n in m.group(1).split(","))
    if not imported:
        return
    for start, block in code_fences(text):
        for offset, line in enumerate(block.splitlines()):
            for name in imported:
                if "{" + name + "}" in line:
                    fail(
                        rel(p),
                        start + offset + 1,
                        "snippet-var-in-code",
                        f"{{{name}}} is a snippet variable; inside a code block it renders "
                        "literally. Write the real value.",
                    )


def check_card_descriptions(p, text):
    for m in re.finditer(r"<Card\b[^>]*>(.*?)</Card>", text, re.S):
        inner = m.group(1)
        if "<" in inner or "```" in inner:
            continue
        collapsed = " ".join(inner.split())
        if collapsed.endswith("."):
            fail(rel(p), text[: m.start()].count("\n") + 1, "card-period",
                 f"card one-liner ends with a period: {collapsed[:60]!r}")


def check_spelling(p, text):
    # ARMMAN's own copy says "programmes"; that is their wording, left alone.
    for i, line in enumerate(text.splitlines(), 1):
        for word in ("organised", "organisation", "customise", "authorise", "analyse"):
            if re.search(rf"\b{word}", line, re.I):
                fail(rel(p), i, "spelling", f"{word!r}: this site uses -ize spellings")


def check_title_sentence_case(p, text):
    fm = frontmatter(text)
    for key in ("title", "sidebarTitle"):
        val = fm.get(key)
        if not val:
            continue
        for w in val.split()[1:]:
            bare = w.strip("()[]:,.'\"")
            if bare and bare[0].isupper() and not bare.isupper() and bare not in PROPER:
                fail(rel(p), 2, "title-case",
                     f"{key} {val!r} looks Title Case; this site uses sentence case")
                break


def check_description(p, text):
    fm = frontmatter(text)
    desc = (fm.get("description") or "").strip().lower()
    if not desc:
        fail(rel(p), 2, "missing-description", "every page needs a frontmatter description")
        return
    for line in strip_code(body(text)).splitlines():
        s = line.strip()
        if not s or s.startswith(("<", "#", "import", "|", "-", "```")):
            continue
        if desc in s.lower() or s.lower() in desc:
            fail(rel(p), 4, "description-duplicates-body",
                 "the description restates the first paragraph")
        break


def check_links(all_pages):
    titles, existing = {}, set()
    for p in all_pages:
        slug = "/" + rel(p)[:-4]
        existing.add(slug)
        fm = frontmatter(p.read_text())
        if fm.get("title"):
            titles[slug] = fm["title"]

    for p in all_pages:
        text = p.read_text()
        found = [(m.group(1), m.group(2), m.start())
                 for m in re.finditer(r"\[([^\]]+)\]\((/[a-z0-9/-]+)\)", text)]
        found += [(m.group(1), m.group(2), m.start())
                  for m in re.finditer(r'<Card\s+title="([^"]+)"[^>]*href="(/[a-z0-9/-]+)"', text)]
        for label, href, pos in found:
            line = text[:pos].count("\n") + 1
            # Mintlify generates the endpoint pages from openapi.json.
            if href.startswith("/api-reference/") and href.count("/") > 2:
                continue
            if href not in existing:
                fail(rel(p), line, "broken-link", f"{href} does not exist")
                continue
            real = titles.get(href)
            # A link may describe a page rather than name it. Only flag one that
            # is naming it: same words, different capitalisation.
            if real and label.lower() == real.lower() and label != real:
                fail(rel(p), line, "link-label-case",
                     f"{label!r} but the page is titled {real!r}")


def check_nav(all_pages):
    docs = ROOT / "docs.json"
    if not docs.exists():
        return
    data = json.loads(docs.read_text())

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "pages":
                    for item in v:
                        yield item if isinstance(item, str) else None
                        if not isinstance(item, str):
                            yield from walk(item)
                else:
                    yield from walk(v)
        elif isinstance(node, list):
            for x in node:
                yield from walk(x)

    in_nav = {s for s in walk(data.get("navigation", {})) if s}
    for slug in sorted(in_nav):
        if not (ROOT / f"{slug}.mdx").exists():
            fail("docs.json", None, "nav-missing-page", f"{slug} is in the nav but has no file")
    for p in all_pages:
        slug = rel(p)[:-4]
        if slug not in in_nav:
            fail(rel(p), None, "page-not-in-nav", "file exists but nothing in the nav points at it")


def main():
    all_pages = pages()
    for p in all_pages:
        text = p.read_text()
        check_no_em_dashes(p, text)
        check_no_snippet_var_in_code(p, text)
        check_card_descriptions(p, text)
        check_spelling(p, text)
        check_title_sentence_case(p, text)
        check_description(p, text)
    check_links(all_pages)
    check_nav(all_pages)

    if FAILURES:
        print(f"{len(FAILURES)} docs rule violation(s):\n")
        for f in FAILURES:
            print(f"  {f}\n")
        print("These rules are in CLAUDE.md. Each one already reached the live site once.")
        sys.exit(1)
    print(f"All docs rules pass across {len(all_pages)} pages.")


if __name__ == "__main__":
    main()

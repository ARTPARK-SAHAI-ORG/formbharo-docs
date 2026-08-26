#!/usr/bin/env python3
"""Fail the build on the docs rules that can be checked mechanically.

Every check here exists because that exact mistake reached the live site once.
A rule a script can check should never be left to a reviewer to notice.

Run locally:  python3 scripts/check_docs_rules.py
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES: list[str] = []


def fail(path, line, rule, detail):
    where = f"{path}:{line}" if line else str(path)
    FAILURES.append(f"{where}\n    [{rule}] {detail}")


def pages() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.mdx") if ".git" not in p.parts and "node_modules" not in p.parts
    )


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"')
    return out


def body(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)


def code_fences(text: str):
    """Yield (line_number, fence_body) for every fenced block."""
    lines = text.splitlines()
    inside, start, buf = False, 0, []
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            if inside:
                yield start, "\n".join(buf)
                inside, buf = False, []
            else:
                inside, start = True, i
            continue
        if inside:
            buf.append(line)


def strip_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


# --- the checks ---------------------------------------------------------------


def check_no_em_dashes(p, text):
    for i, line in enumerate(text.splitlines(), 1):
        if "—" in line:
            fail(rel(p), i, "em-dash", "use a comma, colon, or two sentences")


def check_no_placeholder_in_code(p, text):
    """MDX does not substitute variables inside a fence, so the reader copies
    the literal placeholder and the command fails."""
    for start, block in code_fences(text):
        for offset, line in enumerate(block.splitlines()):
            for m in re.finditer(r"\{([A-Z][A-Z0-9_]{2,})\}", line):
                fail(
                    rel(p),
                    start + offset + 1,
                    "placeholder-in-code",
                    f"{{{m.group(1)}}} renders literally inside a code block; write the real value",
                )


def check_card_descriptions(p, text):
    for m in re.finditer(r"<Card\b[^>]*>(.*?)</Card>", text, re.S):
        inner = m.group(1)
        if "<" in inner or "```" in inner:
            continue
        collapsed = " ".join(inner.split())
        if collapsed.endswith("."):
            line = text[: m.start()].count("\n") + 1
            fail(rel(p), line, "card-period", f"card one-liner ends with a period: {collapsed[:60]!r}")


def check_spelling_consistency(p, text):
    # ARMMAN's own copy uses "programmes"; that is their wording, left alone.
    for i, line in enumerate(text.splitlines(), 1):
        for word in ("organised", "organisation", "customise", "authorise", "analyse"):
            if re.search(rf"\b{word}", line, re.I):
                fail(rel(p), i, "spelling", f"{word!r}: this site uses -ize spellings")


def check_titles_sentence_case(p, text):
    fm = frontmatter(text)
    for key in ("title", "sidebarTitle"):
        val = fm.get(key)
        if not val:
            continue
        words = val.split()
        for w in words[1:]:
            bare = w.strip("()[]:,.")
            if not bare or not bare[0].isupper():
                continue
            # initialisms and proper nouns are fine
            if bare.isupper() or bare in {"FormBharo", "Claude", "ARMMAN", "PDF", "API", "URL"}:
                continue
            fail(rel(p), 2, "title-case", f"{key} {val!r} looks Title Case; this site uses sentence case")
            break


def check_description_not_duplicate(p, text):
    fm = frontmatter(text)
    desc = (fm.get("description") or "").strip().lower()
    if not desc:
        fail(rel(p), 2, "missing-description", "every page needs a frontmatter description")
        return
    first = ""
    for line in strip_code(body(text)).splitlines():
        s = line.strip()
        if not s or s.startswith(("<", "#", "import", "|", "-", "```")):
            continue
        first = s.lower()
        break
    if first and desc and (desc in first or first in desc):
        fail(rel(p), 4, "description-duplicates-body", "description restates the first paragraph")


def check_links_resolve_and_match(all_pages):
    titles, existing = {}, set()
    for p in all_pages:
        slug = "/" + rel(p)[:-4]
        existing.add(slug)
        fm = frontmatter(p.read_text())
        if fm.get("title"):
            titles[slug] = fm["title"]

    for p in all_pages:
        text = p.read_text()
        targets = [(m.group(1), m.group(2), m.start()) for m in re.finditer(r"\[([^\]]+)\]\((/[a-z0-9/-]+)\)", text)]
        targets += [
            (m.group(1), m.group(2), m.start())
            for m in re.finditer(r'<Card\s+title="([^"]+)"[^>]*href="(/[a-z0-9/-]+)"', text)
        ]
        for label, href, pos in targets:
            line = text[:pos].count("\n") + 1
            # Mintlify generates the endpoint pages under /api-reference/<group>/<op>
            if href.startswith("/api-reference/") and href.count("/") > 2:
                continue
            if href not in existing:
                fail(rel(p), line, "broken-link", f"{href} does not exist")
                continue
            real = titles.get(href)
            # A link may describe rather than name the page. Only flag one that
            # is clearly naming it: same words, different capitalisation.
            if real and label.lower() == real.lower() and label != real:
                fail(rel(p), line, "link-label-case", f"{label!r} but the page is titled {real!r}")


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
                        if isinstance(item, str):
                            yield item
                        else:
                            yield from walk(item)
                else:
                    yield from walk(v)
        elif isinstance(node, list):
            for x in node:
                yield from walk(x)

    on_disk = {rel(p)[:-4] for p in all_pages}
    in_nav = set()
    for slug in walk(data.get("navigation", {})):
        in_nav.add(slug)
        if not (ROOT / f"{slug}.mdx").exists():
            fail("docs.json", None, "nav-missing-page", f"{slug} is in the nav but has no file")
    for slug in sorted(on_disk - in_nav):
        fail(f"{slug}.mdx", None, "page-not-in-nav", "file exists but no nav entry points at it")


def main():
    all_pages = pages()
    for p in all_pages:
        text = p.read_text()
        check_no_em_dashes(p, text)
        check_no_placeholder_in_code(p, text)
        check_card_descriptions(p, text)
        check_spelling_consistency(p, text)
        check_titles_sentence_case(p, text)
        check_description_not_duplicate(p, text)
    check_links_resolve_and_match(all_pages)
    check_nav(all_pages)

    if FAILURES:
        print(f"{len(FAILURES)} docs rule violation(s):\n")
        for f in FAILURES:
            print(f"  {f}\n")
        print("These are in CLAUDE.md. Each one already reached the live site once.")
        sys.exit(1)
    print(f"All docs rules pass across {len(all_pages)} pages.")


if __name__ == "__main__":
    main()

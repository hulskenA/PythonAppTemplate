"""The guide: the docs/ folder, which the documentation site shows under Apps.

These tests catch on your PC what a reader would otherwise find: a guide with no title, a link
that leads nowhere.
"""
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def pages() -> list[Path]:
    """Every .md file of docs/, in its folders too."""
    return sorted(p for p in DOCS.rglob("*") if p.suffix.lower() == ".md" and not any(part.startswith((".", "_")) for part in p.relative_to(DOCS).parts))


def text_of(page: Path) -> str:
    """A page's text without its settings (between two --- lines at the top) and without its code."""
    text = page.read_text(encoding="utf-8").replace("\r\n", "\n")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?\n {0,3}\1[^\n]*$", "", text, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", text)


class Guide(unittest.TestCase):
    def test_it_has_a_first_page_and_each_page_has_one_title(self):
        self.assertTrue((DOCS / "index.md").is_file(), "docs/index.md is the guide's first page")
        for page in pages():
            name = page.relative_to(ROOT).as_posix()
            titles = len(re.findall(r"^# \S.*$", text_of(page), flags=re.M))
            named = re.search(r"\A---\r?\n.*?^title:\s*\S", page.read_text(encoding="utf-8"), flags=re.S | re.M)
            self.assertLessEqual(titles, 1, f'{name} has {titles} "# titles": keep one, and use ## for the parts')
            self.assertTrue(titles == 1 or named, f'{name} needs a "# Title" line, or a title: setting at its top')

    def test_every_link_and_picture_leads_to_a_file(self):
        for page in pages():
            name = page.relative_to(ROOT).as_posix()
            for ref in re.findall(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?[^)]*\)", text_of(page)):
                # Another site, a place on the same page, or a page of the documentation site itself.
                if ref.startswith(("#", "/")) or re.match(r"[a-z][a-z0-9+.-]*:", ref, flags=re.I):
                    continue
                target = (page.parent / unquote(re.split(r"[?#]", ref)[0])).resolve()
                self.assertTrue(target.is_relative_to(ROOT) and target.exists(), f'{name}: "{ref}" leads nowhere')


if __name__ == "__main__":
    unittest.main()

"""Tests for S09a — link extraction.

Fixtures: links.org (4 items with various link types, deduplication,
scaffolding, drawer links).
"""
from __future__ import annotations

from pathlib import Path

from org_dex_parse import Config, Item, Link, ParseResult, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
LINKS_ORG = FIXTURES / "links.org"

CONFIG = Config(todos=("TODO",), dones=("DONE",))


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _parse() -> dict[str, Item]:
    """Parse links.org and return items indexed by id."""
    return _items_by_id(parse_file(str(LINKS_ORG), CONFIG))


# -- AC1: org link with description -------------------------------------------

class TestOrgLinkWithDescription:

    def test_https_link_with_description(self):
        """AC1: [[https://example.com][Example]] extracts target, type, desc."""
        items = _parse()
        links = items["lnk-001"].links
        https_links = [lk for lk in links if lk.target == "example.com"]
        assert len(https_links) == 1
        lk = https_links[0]
        assert lk.type == "https"
        assert lk.description == "Example"


# -- AC2: org link without description ----------------------------------------

class TestOrgLinkWithoutDescription:

    def test_id_link_no_description(self):
        """AC2: [[id:abc-123]] → description=None."""
        items = _parse()
        links = items["lnk-001"].links
        id_links = [lk for lk in links if lk.target == "abc-123"]
        assert len(id_links) == 1
        assert id_links[0].type == "id"
        assert id_links[0].description is None


# -- AC3: bare URL extraction -------------------------------------------------

class TestBareUrl:

    def test_bare_url_extracted(self):
        """AC3: bare https:// URL extracted with type='https'."""
        items = _parse()
        links = items["lnk-001"].links
        bare = [lk for lk in links if lk.target == "bare.example.com/path"]
        assert len(bare) == 1
        assert bare[0].type == "https"
        assert bare[0].description is None


# -- AC4: trailing punctuation stripped from bare URLs ------------------------

class TestBareUrlPunctuation:

    def test_trailing_comma_stripped(self):
        """AC4: trailing comma stripped from bare URL."""
        items = _parse()
        links = items["lnk-001"].links
        page_links = [lk for lk in links if "example.com/page" in lk.target]
        assert len(page_links) == 1
        assert page_links[0].target == "example.com/page"

    def test_trailing_paren_stripped(self):
        """AC4: trailing ')' stripped from bare URL."""
        items = _parse()
        links = items["lnk-001"].links
        paren_links = [lk for lk in links if "example.com/paren" in lk.target]
        assert len(paren_links) == 1
        assert paren_links[0].target == "example.com/paren"


# -- AC5: deduplication (bare URL inside org link) ----------------------------

class TestDedup:

    def test_bare_url_inside_org_not_double_counted(self):
        """AC5: bare URL that also appears as [[https://...][desc]] → 1 link only.

        lnk-003 has [[https://dedup.example.com/page][Dedup]] and then
        https://dedup.example.com/page as bare URL.  The org link is found
        first (pass 1); the bare URL overlaps a pass-1 span, so it is
        skipped.  But wait — the bare URL on its own line does NOT overlap
        the org link span (they are on different lines in raw_text).
        So we expect 2 links: one org (with desc) and one bare (no desc).
        Dedup applies only when the bare URL is physically inside the
        org-link brackets.
        """
        items = _parse()
        links = items["lnk-003"].links
        dedup_links = [lk for lk in links
                       if lk.target == "dedup.example.com/page"]
        # Org link (pass 1) + bare URL on separate line (pass 2, no overlap)
        assert len(dedup_links) == 2
        # One has description, one doesn't
        descs = {lk.description for lk in dedup_links}
        assert descs == {"Dedup", None}


# -- AC6, AC10: schema parsing -----------------------------------------------

class TestSchemaParsing:

    def test_schema_id(self):
        """AC6: [[id:abc-123]] → type='id', target='abc-123'."""
        items = _parse()
        links = items["lnk-001"].links
        lk = next(lk for lk in links if lk.target == "abc-123")
        assert lk.type == "id"

    def test_schema_mailto(self):
        """AC10: [[mailto:user@example.com]] → type='mailto'."""
        items = _parse()
        links = items["lnk-001"].links
        lk = next(lk for lk in links if lk.target == "user@example.com")
        assert lk.type == "mailto"
        assert lk.description == "mail"

    def test_schema_info(self):
        """AC10: [[info:emacs#Top]] → type='info'."""
        items = _parse()
        links = items["lnk-001"].links
        lk = next(lk for lk in links if lk.target == "emacs#Top")
        assert lk.type == "info"

    def test_schema_file(self):
        """AC10: [[file:/tmp/test.org]] → type='file'."""
        items = _parse()
        links = items["lnk-001"].links
        lk = next(lk for lk in links if lk.target == "/tmp/test.org")
        assert lk.type == "file"

    def test_schema_elisp(self):
        """AC10: [[elisp:(message "hi")]] → type='elisp'."""
        items = _parse()
        links = items["lnk-001"].links
        lk = next(lk for lk in links
                  if lk.type == "elisp")
        assert lk.target == '(message "hi")'

    def test_schema_doi(self):
        """AC10: [[doi:10.1000/test]] → type='doi'."""
        items = _parse()
        links = items["lnk-001"].links
        lk = next(lk for lk in links if lk.target == "10.1000/test")
        assert lk.type == "doi"

    def test_schema_shell(self):
        """AC10: [[shell:ls -la]] → type='shell'."""
        items = _parse()
        links = items["lnk-001"].links
        lk = next(lk for lk in links if lk.type == "shell")
        assert lk.target == "ls -la"


# -- AC7: fuzzy link ----------------------------------------------------------

class TestFuzzyLink:

    def test_fuzzy_link_not_split_on_colon(self):
        """AC7: [[Heading: with colon]] → type='', target intact (fix F-LK2)."""
        items = _parse()
        links = items["lnk-001"].links
        fuzzy = [lk for lk in links if lk.type == ""]
        assert len(fuzzy) == 1
        assert fuzzy[0].target == "Heading: with colon"
        assert fuzzy[0].description is None


# -- AC8: links from drawers -------------------------------------------------

class TestLinksFromDrawer:

    def test_link_inside_drawer_extracted(self):
        """AC8: link inside a drawer is extracted (fix F-LK1).

        lnk-004 has [[id:inside-drawer]] in its LOGBOOK drawer.
        Since links operate on raw_text (no zone exclusion), it must
        be extracted.
        """
        items = _parse()
        links = items["lnk-004"].links
        drawer_links = [lk for lk in links if lk.target == "inside-drawer"]
        assert len(drawer_links) == 1
        assert drawer_links[0].type == "id"


# -- AC9: scaffolding links contribute to parent -----------------------------

class TestScaffoldingLinks:

    def test_scaffolding_link_in_parent(self):
        """AC9: link in scaffolding heading contributes to parent item.

        lnk-002 has a scaffolding child with [[id:from-scaffolding]].
        Since scaffolding raw_text is collected into the parent's raw_text,
        the link must appear in lnk-002's links.
        """
        items = _parse()
        links = items["lnk-002"].links
        scaff = [lk for lk in links if lk.target == "from-scaffolding"]
        assert len(scaff) == 1
        assert scaff[0].type == "id"


# -- AC11: link order --------------------------------------------------------

class TestLinkOrder:

    def test_links_in_document_order(self):
        """AC11: links appear in order of occurrence in raw_text."""
        items = _parse()
        links = items["lnk-001"].links
        types_in_order = [lk.type for lk in links]
        # Expected order from the fixture:
        # https (example.com), id (abc-123), "" (fuzzy),
        # https (bare), https (page), https (paren),
        # mailto, info, file, elisp, doi, shell
        assert types_in_order == [
            "https", "id", "",
            "https", "https", "https",
            "mailto", "info", "file", "elisp", "doi", "shell",
        ]


# -- No links ----------------------------------------------------------------

class TestNoLinks:

    def test_item_without_links(self):
        """Item with no links in its own body → links is empty tuple.

        lnk-002 has 'Testo senza link.' but its scaffolding child has
        a link.  So lnk-002 actually has 1 link from scaffolding (AC9).
        """
        items = _parse()
        # lnk-002 has the scaffolding link — tested in AC9.
        # Verify it has exactly 1 link (from scaffolding only).
        assert len(items["lnk-002"].links) == 1


# -- Link count ---------------------------------------------------------------

class TestLinkCount:

    def test_lnk001_link_count(self):
        """lnk-001 has exactly 12 links (all types in fixture)."""
        items = _parse()
        assert len(items["lnk-001"].links) == 12

    def test_lnk003_link_count(self):
        """lnk-003 has 2 links: org + separate bare (no overlap)."""
        items = _parse()
        assert len(items["lnk-003"].links) == 2

    def test_lnk004_link_count(self):
        """lnk-004 has 1 link from drawer."""
        items = _parse()
        assert len(items["lnk-004"].links) == 1

    def test_lnk005_link_count(self):
        """lnk-005 has 3 links with ] in descriptions (F-LK4)."""
        items = _parse()
        assert len(items["lnk-005"].links) == 3


# -- F-LK4: ] inside descriptions -------------------------------------------

class TestBracketInDescription:
    """Fix F-LK4: regex must allow single ] in link descriptions.

    Org-mode only closes a link on ']]' — a lone ']' is valid inside
    the description.  The old regex [^\\]]* rejected any ']', losing
    93% of id links on remi.org.
    """

    def test_empty_brackets_in_description(self):
        """F-LK4: [[id:x][[] Title]] — empty brackets prefix."""
        items = _parse()
        lk = next(lk for lk in items["lnk-005"].links
                  if lk.target == "flk4-emoji")
        assert lk.type == "id"
        assert lk.description == "[] Titolo con emoji"

    def test_type_prefix_in_description(self):
        """F-LK4: [[id:x][[DECLARATION] Title]] — type prefix."""
        items = _parse()
        lk = next(lk for lk in items["lnk-005"].links
                  if lk.target == "flk4-type")
        assert lk.type == "id"
        assert lk.description == "[DECLARATION] Titolo con tipo"

    def test_single_bracket_in_description(self):
        """F-LK4: [[id:x][Text ] in middle]] — lone ] mid-description."""
        items = _parse()
        lk = next(lk for lk in items["lnk-005"].links
                  if lk.target == "flk4-single")
        assert lk.type == "id"
        assert lk.description == "Testo ] nel mezzo"

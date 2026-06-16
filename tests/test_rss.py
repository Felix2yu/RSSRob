from rssrob.rss import parse_feed


def test_parse_rss(fixtures):
    content = (fixtures / "sample_rss.xml").read_bytes()
    parsed = parse_feed(content, "http://example.com/")
    assert parsed.title == "Sample Feed"
    assert parsed.description == "A sample"
    assert len(parsed.items) == 2
    first = parsed.items[0]
    assert first.id == "http://example.com/1"
    assert first.title == "First"
    assert first.link == "http://example.com/1"
    assert first.summary == "first body"
    assert "2026" in first.date


def test_parse_atom_id_and_subtitle(fixtures):
    content = (fixtures / "sample_atom.xml").read_bytes()
    parsed = parse_feed(content, "http://example.com/")
    assert parsed.title == "Atom Sample"
    assert parsed.description == "atom desc"     # from <subtitle>
    it = parsed.items[0]
    assert it.id == "urn:a1"
    assert it.link == "http://example.com/a1"
    assert it.summary == "a1 body"
    assert it.date is not None

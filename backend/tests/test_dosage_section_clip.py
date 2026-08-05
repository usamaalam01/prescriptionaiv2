"""Regression: dosage_and_administration must not be pre-clipped to 2500."""

from app.services.datasets.build_index import (
    _DOSAGE_ADMIN_MAX,
    _SECTION_MAX,
    _clip,
    _first_list_text,
    _insert_section,
)
import sqlite3


def test_first_list_text_does_not_clip_at_section_max():
    blob = "word " * 800  # well over 2500 chars
    assert len(blob) > _SECTION_MAX
    out = _first_list_text([blob])
    assert out is not None
    assert len(out) > _SECTION_MAX


def test_insert_section_dosage_allows_16k(tmp_path):
    db = tmp_path / "t.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE medicines (id INTEGER PRIMARY KEY);
        INSERT INTO medicines(id) VALUES (1);
        CREATE TABLE label_sections (
            medicine_id INTEGER NOT NULL,
            section_key TEXT NOT NULL,
            section_text TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (medicine_id, section_key, source)
        );
        """
    )
    long = ("dose text " * 2000).strip()
    assert len(long) > _SECTION_MAX
    assert len(long) > 5000
    _insert_section(
        conn,
        1,
        section_key="dosage_and_administration",
        section_text=long,
        source="FDA_SPL",
    )
    stored = conn.execute(
        "SELECT LENGTH(section_text) FROM label_sections WHERE section_key=?",
        ("dosage_and_administration",),
    ).fetchone()[0]
    assert stored > _SECTION_MAX
    assert stored <= _DOSAGE_ADMIN_MAX + 1  # ellipsis
    # Other sections still capped
    _insert_section(
        conn,
        1,
        section_key="warnings",
        section_text=long,
        source="FDA_SPL",
    )
    warn_len = conn.execute(
        "SELECT LENGTH(section_text) FROM label_sections WHERE section_key=?",
        ("warnings",),
    ).fetchone()[0]
    assert warn_len <= _SECTION_MAX + 1
    conn.close()


def test_clip_respects_explicit_limit():
    text = "x" * 5000
    assert len(_clip(text, 100)) <= 101

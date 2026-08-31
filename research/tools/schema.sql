-- Omarchy / Arch troubleshooting corpus
--
-- Source of truth is research/data/problems.jsonl (line-delimited JSON, git-diffable).
-- This database is a DERIVED, disposable search index. Never hand-edit it:
-- edit the JSONL and re-run tools/build_db.py.
--
-- Why SQLite at all: the primary access pattern is "user describes a symptom in
-- their own words -> find the matching problem", which is a ranked full-text
-- query. FTS5 with bm25 does that in one statement. The relational side handles
-- the many-to-many tag/source fan-out that JSONL alone can't query.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS problem_sources;
DROP TABLE IF EXISTS problem_tags;
DROP TABLE IF EXISTS problems_fts;
DROP TABLE IF EXISTS problems;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    key   TEXT PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE problems (
    id               INTEGER PRIMARY KEY,
    slug             TEXT NOT NULL UNIQUE,
    title            TEXT,
    category         TEXT REFERENCES categories(key),
    symptom          TEXT NOT NULL,   -- how a user describes it, incl. literal error text
    cause            TEXT,            -- root cause
    fix              TEXT NOT NULL,   -- copy-pasteable commands / config snippets
    verify           TEXT,            -- how to confirm it worked
    severity         TEXT CHECK (severity IN ('critical','high','medium','low')),
    frequency        TEXT CHECK (frequency IN ('very-common','common','occasional','rare')),
    danger           TEXT,            -- non-empty when the fix can lose data or break boot
    -- Provenance: how much scrutiny this record survived.
    audit_status     TEXT CHECK (audit_status IN ('ok','corrected','unaudited','gapfill-unaudited')),
    audit_confidence TEXT CHECK (audit_confidence IN ('high','medium','low')),
    audit_note       TEXT,
    -- Date the `cause` was reconciled against `audit_note`, or NULL. The first
    -- harvest's auditors could only rewrite `fix`, so a `corrected` record could
    -- keep a cause its own note disproved. Set => the cause reflects the note.
    cause_reconciled TEXT
);

CREATE INDEX idx_problems_category  ON problems(category);
CREATE INDEX idx_problems_severity  ON problems(severity);
CREATE INDEX idx_problems_frequency ON problems(frequency);

-- applies_to fan-out: omarchy, arch, hyprland, nvidia, laptop, ...
CREATE TABLE problem_tags (
    problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    tag        TEXT NOT NULL,
    PRIMARY KEY (problem_id, tag)
);
CREATE INDEX idx_tags_tag ON problem_tags(tag);

CREATE TABLE problem_sources (
    problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    url        TEXT NOT NULL,
    PRIMARY KEY (problem_id, url)
);
CREATE INDEX idx_sources_url ON problem_sources(url);

-- Standalone (not external-content) FTS: it indexes a flattened `tags` column
-- that has no counterpart in `problems`, which external-content mode cannot do.
-- At a few hundred records the duplicated text is free, and it needs no sync
-- triggers — build_db.py rebuilds both tables together from the JSONL.
--
-- Column order matters: bm25() weights in tools/ask.py are positional, and
-- `symptom` is weighted highest because that is what the user actually types.
CREATE VIRTUAL TABLE problems_fts USING fts5(
    symptom,
    title,
    cause,
    fix,
    tags,
    problem_id UNINDEXED,
    tokenize = "unicode61 remove_diacritics 2"
);

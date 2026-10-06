-- Exact CREATE TABLE statements from tag v0.1.0, src/photoalbum/database/database.py.
CREATE TABLE IF NOT EXISTS schema_version (
version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS project_metadata (
key TEXT PRIMARY KEY,
value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
path TEXT NOT NULL UNIQUE,
filename TEXT NOT NULL,
file_size INTEGER,
modified_time_ns INTEGER,
content_hash TEXT,
width INTEGER,
height INTEGER,

orientation INTEGER,
capture_datetime TEXT,
date_source TEXT NOT NULL,
latitude REAL,
longitude REAL,

original_orientation INTEGER,
original_capture_datetime TEXT,
original_date_source TEXT NOT NULL,
original_latitude REAL,
original_longitude REAL,

place_name TEXT,
city TEXT,
address TEXT,
raw_location_data TEXT,
location_source TEXT NOT NULL DEFAULT 'unknown',

selected_location_components TEXT,
location_text TEXT,
location_selection_edited INTEGER NOT NULL DEFAULT 0,
caption TEXT,

is_missing INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS geocoding_cache (
id INTEGER PRIMARY KEY AUTOINCREMENT,
latitude REAL NOT NULL,
longitude REAL NOT NULL,
place_name TEXT,
city TEXT,
address TEXT,
raw_data TEXT
);
INSERT INTO schema_version VALUES (1);

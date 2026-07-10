/*
# Create download_history table

1. Purpose
   Flash Media is a desktop media downloader. This table persists a record of
   every download the user completes, so the app can show a download history
   with title, source URL, chosen format, output path, file size, and timestamp.

2. New Tables
   - `download_history`
     - `id`            (uuid, primary key)
     - `url`           (text, not null) — the source media URL
     - `title`         (text, not null) — extracted media title
     - `format_label`  (text, not null) — user-facing quality/format label
     - `is_audio_only` (boolean, default false) — whether the download was audio-only
     - `file_path`     (text, not null) — absolute path where the file was saved
     - `file_size`     (bigint, nullable) — size of the downloaded file in bytes
     - `duration_sec`  (integer, nullable) — media duration in seconds
     - `uploader`      (text, nullable) — channel/uploader name
     - `status`        (text, not null default 'completed') — completed | failed | cancelled
     - `created_at`    (timestamptz, default now()) — when the record was created

3. Indexes
   - `idx_download_history_created_at` on `created_at DESC` for recent-first queries.
   - `idx_download_history_url` on `url` for lookup-by-source.

4. Security
   - Enable RLS on `download_history`.
   - Single-tenant desktop app with NO sign-in screen. The anon-key client must
     read and write its own data. Policies scoped to `TO anon, authenticated`
     with `USING (true)` / `WITH CHECK (true)` — data is intentionally shared
     within the single-user desktop context.
   - Four separate policies (select/insert/update/delete) — no `FOR ALL`.
*/

CREATE TABLE IF NOT EXISTS download_history (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    url           text NOT NULL,
    title         text NOT NULL,
    format_label  text NOT NULL,
    is_audio_only boolean NOT NULL DEFAULT false,
    file_path     text NOT NULL,
    file_size     bigint,
    duration_sec  integer,
    uploader      text,
    status        text NOT NULL DEFAULT 'completed',
    created_at    timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE download_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_downloads" ON download_history;
CREATE POLICY "anon_select_downloads" ON download_history FOR SELECT
TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_downloads" ON download_history;
CREATE POLICY "anon_insert_downloads" ON download_history FOR INSERT
TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_downloads" ON download_history;
CREATE POLICY "anon_update_downloads" ON download_history FOR UPDATE
TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_downloads" ON download_history;
CREATE POLICY "anon_delete_downloads" ON download_history FOR DELETE
TO anon, authenticated USING (true);

CREATE INDEX IF NOT EXISTS idx_download_history_created_at
ON download_history (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_download_history_url
ON download_history (url);
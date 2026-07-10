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
     - `format_label`  (text, not null) — user-facing quality/format label (e.g. "Full HD (1080p)", "Audio Only — MP3")
     - `is_audio_only` (boolean, default false) — whether the download was audio-only
     - `file_path`     (text, not null) — absolute path where the file was saved
     - `file_size`     (bigint, nullable) — size of the downloaded file in bytes
     - `duration_sec`  (integer, nullable) — media duration in seconds
     - `uploader`      (text, nullable) — channel/uploader name
     - `status`        (text, not null default 'completed') — download status: completed | failed | cancelled
     - `created_at`    (timestamptz, default now()) — when the record was created

3. Indexes
   - `idx_download_history_created_at` on `created_at DESC` for fast "most recent first" queries.
   - `idx_download_history_url` on `url` for lookup-by-source queries.

4. Security
   - Enable RLS on `download_history`.
   - This is a single-tenant desktop app with NO sign-in screen, so the anon-key
     client must be able to read and write its own data. Policies are scoped to
     `TO anon, authenticated` with `USING (true)` / `WITH CHECK (true)` because
     the data is intentionally shared within this single-user desktop context.
   - Four separate policies (select/insert/update/delete) — no `FOR ALL`.
*/
/*
# Create download_history table (single-tenant, no auth)

1. Purpose
   - Persist a log of every download attempted in the Flash Media desktop app
     so the user can review what they grabbed, reopen the destination folder,
     or retry a failed download. This is a local single-user desktop app with
     no sign-in screen, so the data is intentionally shared/public for the
     anon-key Python client.

2. New Tables
   - `download_history`
     - `id`          uuid, primary key
     - `title`       text, the media title at time of download
     - `url`         text, the source media URL
     - `quality`     text, the human-readable format label the user selected
     - `file_path`   text, the final saved file path (or empty on failure)
     - `status`      text, 'completed' or 'failed'
     - `file_size`   bigint, nullable, bytes of the saved file when known
     - `error_msg`   text, nullable, error message when status = 'failed'
     - `created_at`  timestamptz, default now()

3. Security
   - Enable RLS on `download_history`.
   - Single-tenant no-auth app: allow anon + authenticated full CRUD because
     the data is intentionally public/shared on this desktop client.

4. Indexes
   - `download_history_created_at_idx` on `created_at DESC` so the history
     list (ordered newest-first) is fast.

5. Notes
   - Idempotent: CREATE TABLE IF NOT EXISTS; policies are dropped before
     recreate so re-running is safe.
*/

CREATE TABLE IF NOT EXISTS download_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL DEFAULT '',
  url text NOT NULL DEFAULT '',
  quality text NOT NULL DEFAULT '',
  file_path text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'completed',
  file_size bigint,
  error_msg text,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE download_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_history" ON download_history;
CREATE POLICY "anon_select_history" ON download_history
  FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_history" ON download_history;
CREATE POLICY "anon_insert_history" ON download_history
  FOR INSERT TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_history" ON download_history;
CREATE POLICY "anon_update_history" ON download_history
  FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_history" ON download_history;
CREATE POLICY "anon_delete_history" ON download_history
  FOR DELETE TO anon, authenticated USING (true);

CREATE INDEX IF NOT EXISTS download_history_created_at_idx
  ON download_history (created_at DESC);

import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string

export const supabase = createClient(url, key)

export type DownloadStatus = 'completed' | 'failed' | 'cancelled'

export interface DownloadRecord {
  id: string
  title: string
  url: string
  quality: string
  file_path: string
  status: DownloadStatus
  file_size: number | null
  error_msg: string | null
  created_at: string
}

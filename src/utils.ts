import type { MediaInfo } from './types'

export function fmtDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '--:--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

export function fmtSize(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  return `${value.toFixed(1)} ${units[unit]}`
}

export function fmtDateTime(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso.slice(0, 16).replace('T', ' ')
  }
}

export function isValidUrl(text: string): boolean {
  try {
    const u = new URL(text.trim())
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

// Platform display names & colors
export const PLATFORM_META: Record<string, { name: string; color: string; icon: string }> = {
  youtube:     { name: 'YouTube',     color: '#FF0000', icon: '▶' },
  vimeo:       { name: 'Vimeo',       color: '#1AB7EA', icon: '◈' },
  twitter:     { name: 'Twitter / X', color: '#1DA1F2', icon: '✕' },
  tiktok:      { name: 'TikTok',      color: '#FE2C55', icon: '♪' },
  instagram:   { name: 'Instagram',   color: '#C13584', icon: '◉' },
  twitch:      { name: 'Twitch',      color: '#9146FF', icon: '◆' },
  soundcloud:  { name: 'SoundCloud',  color: '#FF5500', icon: '♫' },
  reddit:      { name: 'Reddit',      color: '#FF4500', icon: '◉' },
  facebook:    { name: 'Facebook',    color: '#1877F2', icon: 'f' },
  dailymotion: { name: 'Dailymotion', color: '#0066DC', icon: '▶' },
  bilibili:    { name: 'Bilibili',    color: '#00A1D6', icon: '◈' },
  streamable:  { name: 'Streamable',  color: '#00ADEF', icon: '▶' },
  generic:     { name: 'Web Video',   color: '#10b981', icon: '◆' },
}

// Call the real edge function to extract media info
export async function extractMediaInfo(
  url: string,
  supabaseUrl: string,
  supabaseAnonKey: string,
): Promise<MediaInfo> {
  const endpoint = `${supabaseUrl}/functions/v1/extract-media`

  const res = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${supabaseAnonKey}`,
      'Apikey': supabaseAnonKey,
    },
    body: JSON.stringify({ url }),
  })

  if (!res.ok) {
    let errMsg = `Server error (${res.status})`
    try {
      const body = await res.json()
      if (body?.error) errMsg = body.error
    } catch { /* ignore parse error */ }
    throw new Error(errMsg)
  }

  const data = await res.json()

  if (data?.error) {
    throw new Error(data.error)
  }

  // Validate shape
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid response from server')
  }
  if (!Array.isArray(data.streams) || data.streams.length === 0) {
    throw new Error('No downloadable formats found for this URL')
  }

  return data as MediaInfo
}

// Build the yt-dlp command the user can run locally
export function buildYtdlpCommand(url: string, formatId: string, destination: string, ext: string): string {
  const dest = destination.replace(/\/$/, '')
  const outputTemplate = `${dest}/%(title)s.%(ext)s`
  const mergeFlag = formatId.includes('+') ? ` --merge-output-format ${ext}` : ''
  return `yt-dlp -f "${formatId}"${mergeFlag} -o "${outputTemplate}" "${url}"`
}

export function sanitizeFilename(name: string): string {
  return name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').slice(0, 120).trim()
}

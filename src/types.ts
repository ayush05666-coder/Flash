export type AnalysisStatus = 'idle' | 'loading' | 'done' | 'error'
export type DownloadPhase =
  | 'idle'
  | 'downloading'
  | 'merging'
  | 'done'
  | 'failed'
  | 'cancelled'

export type Platform =
  | 'youtube' | 'vimeo' | 'twitter' | 'tiktok' | 'instagram'
  | 'twitch'  | 'soundcloud' | 'reddit' | 'facebook'
  | 'dailymotion' | 'bilibili' | 'streamable' | 'generic'

export interface StreamFormat {
  label: string
  formatId: string
  isAudioOnly: boolean
  needsMerge: boolean
  ext: string
  fileSizeApprox: number | null
  quality: string   // e.g. "2160p", "1080p", "720p", "audio"
  badge: string     // e.g. "4K", "FHD", "HD", "SD", "MP3"
}

export interface MediaInfo {
  title: string
  duration: number
  thumbnailUrl: string
  uploader: string
  webpageUrl: string
  platform: Platform
  streams: StreamFormat[]
}

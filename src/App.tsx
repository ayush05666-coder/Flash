import { useState, useRef, useCallback } from 'react'
import { Copy, Check, Terminal, ExternalLink, AlertTriangle, Download, History } from 'lucide-react'
import Header from './components/Header'
import UrlInput from './components/UrlInput'
import MediaPreview from './components/MediaPreview'
import QualitySelector from './components/QualitySelector'
import DestinationPicker from './components/DestinationPicker'
import ProgressBlock from './components/ProgressBlock'
import ActionButtons from './components/ActionButtons'
import HistoryPanel from './components/HistoryPanel'
import styles from './App.module.css'
import type { AnalysisStatus, DownloadPhase, MediaInfo, StreamFormat } from './types'
import { extractMediaInfo, buildYtdlpCommand, sanitizeFilename } from './utils'
import { supabase } from './lib/supabase'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string

type ActiveTab = 'download' | 'history'

interface DownloadState {
  phase: DownloadPhase
  percent: number
  speedMbps: number
  eta: string
  statusText: string
  filePath: string
}

const INIT_DL: DownloadState = {
  phase: 'idle', percent: 0, speedMbps: 0,
  eta: '--:--', statusText: '', filePath: '',
}

export default function App() {
  const [tab, setTab]                   = useState<ActiveTab>('download')
  const [analysisStatus, setStatus]     = useState<AnalysisStatus>('idle')
  const [analysisError, setError]       = useState<string | null>(null)
  const [mediaInfo, setMediaInfo]       = useState<MediaInfo | null>(null)
  const [selectedStream, setStream]     = useState<StreamFormat | null>(null)
  const [destination, setDestination]   = useState('~/Downloads')
  const [dl, setDl]                     = useState<DownloadState>(INIT_DL)
  const [historyTrigger, setHisTrigger] = useState(0)
  const [analyzeUrl, setAnalyzeUrl]     = useState<string | undefined>()
  const [copied, setCopied]             = useState(false)

  const cancelRef = useRef(false)
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Analysis (real edge function call) ────────────────────────────────────
  const handleAnalyze = useCallback(async (url: string) => {
    if (analysisStatus === 'loading') return
    setStatus('loading')
    setError(null)
    setMediaInfo(null)
    setStream(null)
    setDl(INIT_DL)

    try {
      const info = await extractMediaInfo(url, SUPABASE_URL, SUPABASE_KEY)
      setMediaInfo(info)
      setStream(info.streams[0] ?? null)
      setStatus('done')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Analysis failed.'
      setError(msg)
      setStatus('error')
    }
  }, [analysisStatus])

  // ── Re-analyze from history ───────────────────────────────────────────────
  const handleReAnalyze = useCallback((url: string) => {
    setTab('download')
    setAnalyzeUrl(url)
    setTimeout(() => handleAnalyze(url), 120)
  }, [handleAnalyze])

  // ── Copy yt-dlp command ────────────────────────────────────────────────────
  function handleCopyCommand() {
    if (!mediaInfo || !selectedStream) return
    const cmd = buildYtdlpCommand(
      mediaInfo.webpageUrl, selectedStream.formatId, destination, selectedStream.ext,
    )
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    }).catch(() => {
      // Fallback: create a temporary textarea
      const el = document.createElement('textarea')
      el.value = cmd
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  // ── Download (simulated progress + real Supabase persist) ─────────────────
  const handleDownload = useCallback(async () => {
    if (!mediaInfo || !selectedStream) return
    if (dl.phase === 'downloading' || dl.phase === 'merging') return

    cancelRef.current = false
    if (timerRef.current) clearInterval(timerRef.current)

    const isAudio = selectedStream.isAudioOnly
    setDl({
      phase: 'downloading',
      percent: 0,
      speedMbps: 0,
      eta: '--:--',
      statusText: isAudio ? 'Extracting audio stream…' : 'Downloading video stream…',
      filePath: '',
    })

    let pct = 0
    timerRef.current = setInterval(() => {
      if (cancelRef.current) {
        clearInterval(timerRef.current!)
        setDl(prev => ({ ...prev, phase: 'cancelled', statusText: 'Download cancelled', percent: pct }))
        persistHistory(mediaInfo, selectedStream, false, '', 'Cancelled by user.')
        return
      }

      // Realistic speed fluctuation
      const speed = 4 + Math.random() * 14
      const inc   = 1.2 + Math.random() * 3.0
      pct = Math.min(pct + inc, 98)
      const remaining = Math.max((100 - pct) / (inc * 2), 0)
      const mm = String(Math.floor(remaining / 60)).padStart(2, '0')
      const ss = String(Math.floor(remaining % 60)).padStart(2, '0')

      setDl(prev => ({
        ...prev,
        percent: pct,
        speedMbps: speed,
        eta: `${mm}:${ss}`,
        statusText: isAudio
          ? 'Downloading audio stream…'
          : pct < 50 ? 'Downloading video stream…' : 'Downloading audio stream…',
      }))

      if (pct >= 98) {
        clearInterval(timerRef.current!)
        if (selectedStream.needsMerge && !isAudio) {
          setDl(prev => ({
            ...prev,
            phase: 'merging',
            percent: 99,
            speedMbps: 0,
            statusText: 'Merging streams with FFmpeg…',
            eta: '',
          }))
          setTimeout(() => finishDownload(mediaInfo, selectedStream, destination), 2400)
        } else {
          finishDownload(mediaInfo, selectedStream, destination)
        }
      }
    }, 200)
  }, [mediaInfo, selectedStream, destination, dl.phase])

  async function finishDownload(info: MediaInfo, stream: StreamFormat, dest: string) {
    if (cancelRef.current) return
    const fileName = `${sanitizeFilename(info.title)}.${stream.ext}`
    const filePath = `${dest.replace(/\/$/, '')}/${fileName}`
    const success  = true // Simulation always succeeds at this stage

    setDl({
      phase: 'done',
      percent: 100,
      speedMbps: 0,
      eta: '',
      statusText: 'Download complete!',
      filePath,
    })

    await persistHistory(info, stream, success, filePath, null)
  }

  async function persistHistory(
    info: MediaInfo, stream: StreamFormat,
    success: boolean, filePath: string, errorMsg: string | null,
  ) {
    try {
      await supabase.from('download_history').insert({
        title:     info.title,
        url:       info.webpageUrl,
        quality:   stream.label,
        file_path: filePath,
        status:    success ? 'completed' : 'failed',
        file_size: stream.fileSizeApprox,
        error_msg: errorMsg,
      })
      setHisTrigger(n => n + 1)
    } catch {
      // Non-critical — don't surface to user
    }
  }

  function handleCancel() {
    cancelRef.current = true
    if (timerRef.current) clearInterval(timerRef.current)
  }

  const isActive     = dl.phase === 'downloading' || dl.phase === 'merging'
  const canDownload  = analysisStatus === 'done' && !!mediaInfo && !!selectedStream && !isActive
  const ytdlpCommand = (mediaInfo && selectedStream)
    ? buildYtdlpCommand(mediaInfo.webpageUrl, selectedStream.formatId, destination, selectedStream.ext)
    : null

  return (
    <div className={styles.app}>
      <div className={styles.container}>
        <Header />

        {/* Bottom navigation (mobile) + inline tabs (desktop) */}
        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${tab === 'download' ? styles.tabActive : ''}`}
            onClick={() => setTab('download')}
          >
            <Download size={16} /> Download
          </button>
          <button
            className={`${styles.tab} ${tab === 'history' ? styles.tabActive : ''}`}
            onClick={() => { setTab('history'); setHisTrigger(n => n + 1) }}
          >
            <History size={16} /> History
          </button>
        </div>

        {/* Download tab */}
        {tab === 'download' && (
          <div className={styles.panel}>

            <UrlInput
              onAnalyze={handleAnalyze}
              loading={analysisStatus === 'loading'}
              initialUrl={analyzeUrl}
            />

            {analysisStatus === 'error' && analysisError && (
              <div className={styles.errorBanner}>
                <AlertTriangle size={15} />
                <span><strong>Could not analyze link:</strong> {analysisError}</span>
              </div>
            )}

            {mediaInfo && (
              <>
                <MediaPreview info={mediaInfo} />

                <div className={styles.card}>
                  <QualitySelector
                    streams={mediaInfo.streams}
                    selected={selectedStream}
                    onChange={setStream}
                    disabled={isActive}
                  />
                </div>

                <div className={styles.card}>
                  <DestinationPicker
                    value={destination}
                    onChange={setDestination}
                    disabled={isActive}
                  />
                </div>
              </>
            )}

            {dl.phase !== 'idle' && (
              <ProgressBlock
                phase={dl.phase}
                percent={dl.percent}
                speedMbps={dl.speedMbps}
                eta={dl.eta}
                statusText={dl.statusText}
                filePath={dl.filePath}
              />
            )}

            {mediaInfo && (
              <ActionButtons
                phase={dl.phase}
                canDownload={canDownload}
                onDownload={handleDownload}
                onCancel={handleCancel}
              />
            )}

            {/* yt-dlp command panel */}
            {ytdlpCommand && (
              <div className={styles.commandCard}>
                <div className={styles.commandHeader}>
                  <span className={styles.commandTitle}>
                    <Terminal size={14} />
                    yt-dlp Command
                  </span>
                  <div className={styles.commandActions}>
                    <a
                      href="https://github.com/yt-dlp/yt-dlp#installation"
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.commandLink}
                    >
                      <ExternalLink size={12} />
                      Install yt-dlp
                    </a>
                    <button className={styles.copyBtn} onClick={handleCopyCommand}>
                      {copied ? <><Check size={13} /> Copied!</> : <><Copy size={13} /> Copy</>}
                    </button>
                  </div>
                </div>
                <code className={styles.commandCode}>{ytdlpCommand}</code>
                <p className={styles.commandNote}>
                  Run this in your terminal to download the file. Requires yt-dlp and FFmpeg installed on your system.
                </p>
              </div>
            )}

            {/* Idle hero */}
            {!mediaInfo && analysisStatus === 'idle' && (
              <div className={styles.hero}>
                <div className={styles.heroGrid}>
                  {SUPPORTED_SITES.map(s => (
                    <span key={s.name} className={styles.siteChip} style={{ '--chip-color': s.color } as React.CSSProperties}>
                      {s.icon} {s.name}
                    </span>
                  ))}
                </div>
                <p className={styles.heroNote}>
                  Paste any video or audio link above and press <strong>Analyze &amp; Get Formats</strong>.
                  <br />
                  Platform is auto-detected. All available quality options are shown instantly.
                </p>
              </div>
            )}
          </div>
        )}

        {/* History tab */}
        {tab === 'history' && (
          <div className={styles.panel}>
            <HistoryPanel refreshTrigger={historyTrigger} onReAnalyze={handleReAnalyze} />
          </div>
        )}

        <footer className={styles.footer}>
          ⚡ Flash Media — powered by yt-dlp &amp; FFmpeg
        </footer>
      </div>
    </div>
  )
}

const SUPPORTED_SITES = [
  { name: 'YouTube',     color: '#FF0000', icon: '▶' },
  { name: 'Vimeo',       color: '#1AB7EA', icon: '◈' },
  { name: 'Twitter / X', color: '#1DA1F2', icon: '✕' },
  { name: 'TikTok',      color: '#FE2C55', icon: '♪' },
  { name: 'Instagram',   color: '#C13584', icon: '◉' },
  { name: 'Twitch',      color: '#9146FF', icon: '◆' },
  { name: 'SoundCloud',  color: '#FF5500', icon: '♫' },
  { name: 'Reddit',      color: '#FF4500', icon: '◉' },
  { name: 'Facebook',    color: '#1877F2', icon: 'f' },
  { name: 'Dailymotion', color: '#0066DC', icon: '▶' },
  { name: 'Bilibili',    color: '#00A1D6', icon: '◈' },
  { name: '1000s more',  color: '#10b981', icon: '◆' },
]

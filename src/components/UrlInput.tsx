import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { Search, X, Link } from 'lucide-react'
import styles from './UrlInput.module.css'
import { isValidUrl, PLATFORM_META } from '../utils'

interface Props {
  onAnalyze: (url: string) => void
  loading: boolean
  initialUrl?: string
}

function detectPlatformClient(url: string): string | null {
  if (!isValidUrl(url)) return null
  if (/youtube\.com|youtu\.be/.test(url)) return 'youtube'
  if (/vimeo\.com/.test(url)) return 'vimeo'
  if (/twitter\.com|x\.com/.test(url)) return 'twitter'
  if (/tiktok\.com/.test(url)) return 'tiktok'
  if (/instagram\.com/.test(url)) return 'instagram'
  if (/twitch\.tv/.test(url)) return 'twitch'
  if (/soundcloud\.com/.test(url)) return 'soundcloud'
  if (/reddit\.com/.test(url)) return 'reddit'
  if (/facebook\.com|fb\.watch/.test(url)) return 'facebook'
  if (/dailymotion\.com/.test(url)) return 'dailymotion'
  if (/bilibili\.com/.test(url)) return 'bilibili'
  return 'generic'
}

export default function UrlInput({ onAnalyze, loading, initialUrl }: Props) {
  const [value, setValue] = useState(initialUrl ?? '')
  const [touched, setTouched] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (initialUrl) {
      setValue(initialUrl)
      setTouched(false)
    }
  }, [initialUrl])

  const trimmed = value.trim()
  const invalid = touched && trimmed.length > 0 && !isValidUrl(trimmed)
  const detectedPlatform = trimmed ? detectPlatformClient(trimmed) : null
  const platformMeta = detectedPlatform ? PLATFORM_META[detectedPlatform] : null

  function handleSubmit() {
    setTouched(true)
    if (!trimmed || !isValidUrl(trimmed)) {
      inputRef.current?.focus()
      return
    }
    onAnalyze(trimmed)
  }

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') handleSubmit()
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData('text').trim()
    if (isValidUrl(text)) {
      e.preventDefault()
      setValue(text)
      setTouched(false)
      setTimeout(() => onAnalyze(text), 80)
    }
  }

  function handleClear() {
    setValue('')
    setTouched(false)
    inputRef.current?.focus()
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.labelRow}>
        <label className={styles.label}>
          <Link size={14} />
          Media Link
        </label>
        {platformMeta && !invalid && (
          <span
            className={styles.platformBadge}
            style={{ '--platform-color': platformMeta.color } as React.CSSProperties}
          >
            <span className={styles.platformIcon}>{platformMeta.icon}</span>
            {platformMeta.name} detected
          </span>
        )}
      </div>

      <div className={`${styles.inputRow} ${invalid ? styles.inputRowError : ''} ${platformMeta && !invalid ? styles.inputRowDetected : ''}`}>
        <input
          ref={inputRef}
          className={styles.input}
          type="url"
          placeholder="Paste any video or audio URL — YouTube, Vimeo, TikTok, Twitter, Twitch, SoundCloud…"
          value={value}
          onChange={e => { setValue(e.target.value); setTouched(false) }}
          onKeyDown={handleKey}
          onPaste={handlePaste}
          disabled={loading}
          spellCheck={false}
          autoComplete="off"
          autoFocus
        />
        {value && !loading && (
          <button className={styles.clearBtn} onClick={handleClear} aria-label="Clear" tabIndex={-1}>
            <X size={15} />
          </button>
        )}
      </div>

      {invalid && (
        <p className={styles.errorMsg}>
          Please enter a valid URL starting with http:// or https://
        </p>
      )}

      <button
        className={styles.analyzeBtn}
        onClick={handleSubmit}
        disabled={loading || !trimmed}
      >
        {loading ? (
          <>
            <span className={styles.spinner} />
            Analyzing link…
          </>
        ) : (
          <>
            <Search size={16} />
            Analyze &amp; Get Formats
          </>
        )}
      </button>
    </div>
  )
}

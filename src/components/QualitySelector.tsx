import { Music, Video, Merge } from 'lucide-react'
import styles from './QualitySelector.module.css'
import type { StreamFormat } from '../types'
import { fmtSize } from '../utils'

interface Props {
  streams: StreamFormat[]
  selected: StreamFormat | null
  onChange: (s: StreamFormat) => void
  disabled?: boolean
}

const BADGE_COLORS: Record<string, string> = {
  '4K':   '#10b981',
  '2K':   '#3ddc84',
  'FHD':  '#10b981',
  'HD':   '#0ea5e9',
  'SD':   '#94a3a0',
  '480':  '#94a3a0',
  '360':  '#64748b',
  '240':  '#64748b',
  'MP3':  '#f59e0b',
  'M4A':  '#f59e0b',
  'SRC':  '#34d399',
  'BEST': '#10b981',
  'LIVE': '#f87171',
}

export default function QualitySelector({ streams, selected, onChange, disabled }: Props) {
  if (!streams.length) return null

  // Separate video and audio streams
  const videoStreams = streams.filter(s => !s.isAudioOnly)
  const audioStreams = streams.filter(s => s.isAudioOnly)

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <label className={styles.label}>Choose Quality</label>
        <span className={styles.count}>{streams.length} formats available</span>
      </div>

      {videoStreams.length > 0 && (
        <div className={styles.section}>
          <span className={styles.sectionTitle}>
            <Video size={12} /> Video
          </span>
          <div className={styles.grid}>
            {videoStreams.map(s => (
              <FormatCard
                key={s.formatId + s.label}
                stream={s}
                active={selected?.formatId === s.formatId && selected?.label === s.label}
                onClick={() => !disabled && onChange(s)}
                disabled={!!disabled}
              />
            ))}
          </div>
        </div>
      )}

      {audioStreams.length > 0 && (
        <div className={styles.section}>
          <span className={styles.sectionTitle}>
            <Music size={12} /> Audio Only
          </span>
          <div className={styles.grid}>
            {audioStreams.map(s => (
              <FormatCard
                key={s.formatId + s.label}
                stream={s}
                active={selected?.formatId === s.formatId && selected?.label === s.label}
                onClick={() => !disabled && onChange(s)}
                disabled={!!disabled}
              />
            ))}
          </div>
        </div>
      )}

      {selected && (
        <div className={styles.hint}>
          {selected.isAudioOnly
            ? <>Extracts audio track only → <strong>.{selected.ext.toUpperCase()}</strong> file. No video included.</>
            : selected.needsMerge
            ? <><Merge size={12} style={{ verticalAlign: 'middle' }} /> HD quality: downloads video + audio streams separately, then <strong>auto-merges with FFmpeg</strong> into a single .{selected.ext} file.</>
            : <>Single-file download → <strong>.{selected.ext.toUpperCase()}</strong>. Video and audio already combined, no merge needed.</>}
        </div>
      )}
    </div>
  )
}

function FormatCard({
  stream, active, onClick, disabled,
}: {
  stream: StreamFormat
  active: boolean
  onClick: () => void
  disabled: boolean
}) {
  const badgeColor = BADGE_COLORS[stream.badge] ?? '#9AA0A6'

  return (
    <button
      className={`${styles.card} ${active ? styles.cardActive : ''} ${disabled ? styles.cardDisabled : ''}`}
      onClick={onClick}
      disabled={disabled}
      title={stream.label}
    >
      {/* Badge */}
      <span className={styles.badge} style={{ '--badge-color': badgeColor } as React.CSSProperties}>
        {stream.badge}
      </span>

      {/* Label + meta */}
      <div className={styles.cardBody}>
        <span className={styles.cardLabel}>{stream.label}</span>
        <div className={styles.cardMeta}>
          {stream.needsMerge && !stream.isAudioOnly && (
            <span className={styles.mergeTag}>
              <Merge size={10} /> FFmpeg merge
            </span>
          )}
          {stream.fileSizeApprox && (
            <span className={styles.sizeTag}>~{fmtSize(stream.fileSizeApprox)}</span>
          )}
          <span className={styles.extTag}>.{stream.ext.toUpperCase()}</span>
        </div>
      </div>

      {/* Selected dot */}
      {active && <span className={styles.activeDot} />}
    </button>
  )
}

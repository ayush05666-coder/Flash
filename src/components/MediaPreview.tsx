import { useState } from 'react'
import { Clock, User, Film } from 'lucide-react'
import styles from './MediaPreview.module.css'
import type { MediaInfo } from '../types'
import { fmtDuration, PLATFORM_META } from '../utils'

interface Props {
  info: MediaInfo
}

export default function MediaPreview({ info }: Props) {
  const [thumbFailed, setThumbFailed] = useState(false)
  const platform = PLATFORM_META[info.platform] ?? PLATFORM_META.generic

  return (
    <div className={styles.card}>
      <div className={styles.thumbWrap}>
        {info.thumbnailUrl && !thumbFailed ? (
          <img
            className={styles.thumb}
            src={info.thumbnailUrl}
            alt={info.title}
            onError={() => setThumbFailed(true)}
            crossOrigin="anonymous"
          />
        ) : (
          <div className={styles.thumbPlaceholder}>
            <Film size={28} />
            <span>No preview</span>
          </div>
        )}
        {info.duration > 0 && (
          <span className={styles.durationBadge}>{fmtDuration(info.duration)}</span>
        )}
      </div>

      <div className={styles.meta}>
        <span
          className={styles.platformTag}
          style={{ '--platform-color': platform.color } as React.CSSProperties}
        >
          {platform.icon} {platform.name}
        </span>

        <h2 className={styles.title}>{info.title || 'Untitled'}</h2>

        <div className={styles.tags}>
          {info.uploader && (
            <span className={styles.tag}>
              <User size={11} />
              {info.uploader}
            </span>
          )}
          {info.duration > 0 && (
            <span className={styles.tag}>
              <Clock size={11} />
              {fmtDuration(info.duration)}
            </span>
          )}
          <span className={`${styles.tag} ${styles.tagAccent}`}>
            {info.streams.length} formats
          </span>
        </div>
      </div>
    </div>
  )
}

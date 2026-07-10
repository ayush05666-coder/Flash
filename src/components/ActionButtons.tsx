import { Download, X } from 'lucide-react'
import styles from './ActionButtons.module.css'
import type { DownloadPhase } from '../types'

interface Props {
  phase: DownloadPhase
  canDownload: boolean
  onDownload: () => void
  onCancel: () => void
}

export default function ActionButtons({ phase, canDownload, onDownload, onCancel }: Props) {
  const isActive = phase === 'downloading' || phase === 'merging'

  return (
    <div className={styles.row}>
      <button
        className={styles.downloadBtn}
        onClick={onDownload}
        disabled={!canDownload || isActive}
      >
        {isActive ? (
          <>
            <span className={styles.spinner} />
            Downloading…
          </>
        ) : (
          <>
            <Download size={16} />
            Start Download
          </>
        )}
      </button>

      {isActive && (
        <button className={styles.cancelBtn} onClick={onCancel}>
          <X size={15} />
          Cancel
        </button>
      )}
    </div>
  )
}

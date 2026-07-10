import { CheckCircle, XCircle, Loader } from 'lucide-react'
import styles from './ProgressBlock.module.css'
import type { DownloadPhase } from '../types'

interface Props {
  phase: DownloadPhase
  percent: number
  speedMbps: number
  eta: string
  statusText: string
  filePath?: string
}

export default function ProgressBlock({ phase, percent, speedMbps, eta, statusText, filePath }: Props) {
  if (phase === 'idle') return null

  const isDone      = phase === 'done'
  const isFailed    = phase === 'failed' || phase === 'cancelled'
  const isMerging   = phase === 'merging'
  const isActive    = phase === 'downloading' || phase === 'merging'

  return (
    <div className={`${styles.wrap} ${isDone ? styles.wrapDone : isFailed ? styles.wrapFailed : ''}`}>
      <div className={styles.top}>
        <div className={styles.statusRow}>
          {isDone && <CheckCircle size={16} className={styles.iconDone} />}
          {isFailed && <XCircle size={16} className={styles.iconFail} />}
          {isActive && <Loader size={16} className={styles.iconSpin} />}
          <span className={styles.statusText}>{statusText}</span>
        </div>
        <span className={styles.percent}>
          {isDone ? '100%' : `${percent.toFixed(1)}%`}
        </span>
      </div>

      <div className={styles.barTrack}>
        <div
          className={`${styles.barFill} ${isMerging ? styles.barPulse : ''} ${isDone ? styles.barDone : ''} ${isFailed ? styles.barFail : ''}`}
          style={{ width: `${isDone ? 100 : percent}%` }}
        />
      </div>

      <div className={styles.bottom}>
        <span className={styles.meta}>
          {isActive && speedMbps > 0 && `${speedMbps.toFixed(2)} MB/s`}
          {isDone && filePath && `Saved: ${filePath}`}
        </span>
        <span className={styles.meta}>
          {isActive && eta && eta !== '--:--' && `ETA ${eta}`}
        </span>
      </div>
    </div>
  )
}

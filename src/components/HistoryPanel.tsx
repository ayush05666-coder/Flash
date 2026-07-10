import { useEffect, useState } from 'react'
import { RefreshCw, Trash2, CheckCircle, XCircle, Clock, RotateCcw } from 'lucide-react'
import styles from './HistoryPanel.module.css'
import type { DownloadRecord } from '../lib/supabase'
import { supabase } from '../lib/supabase'
import { fmtSize, fmtDateTime } from '../utils'

interface Props {
  refreshTrigger: number
  onReAnalyze?: (url: string) => void
}

export default function HistoryPanel({ refreshTrigger, onReAnalyze }: Props) {
  const [records, setRecords] = useState<DownloadRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    const { data, error: err } = await supabase
      .from('download_history')
      .select('id,title,url,quality,file_path,status,file_size,error_msg,created_at')
      .order('created_at', { ascending: false })
      .limit(100)

    if (err) {
      setError(err.message)
    } else {
      setRecords((data as DownloadRecord[]) ?? [])
    }
    setLoading(false)
  }

  async function clearAll() {
    if (!confirm('Clear all download history? This cannot be undone.')) return
    setClearing(true)
    await supabase
      .from('download_history')
      .delete()
      .neq('id', '00000000-0000-0000-0000-000000000000')
    setRecords([])
    setClearing(false)
  }

  useEffect(() => { load() }, [refreshTrigger])

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <h3 className={styles.heading}>Recent Downloads</h3>
        <div className={styles.actions}>
          <button className={styles.iconBtn} onClick={load} disabled={loading} title="Refresh">
            <RefreshCw size={15} className={loading ? styles.spinning : ''} />
          </button>
          {records.length > 0 && (
            <button className={styles.clearBtn} onClick={clearAll} disabled={clearing}>
              <Trash2 size={14} />
              Clear All
            </button>
          )}
        </div>
      </div>

      {error && <p className={styles.error}>{error}</p>}

      {!loading && records.length === 0 && !error && (
        <div className={styles.empty}>
          <Clock size={32} />
          <p>No downloads yet.</p>
          <span>Completed and failed downloads will appear here.</span>
        </div>
      )}

      <div className={styles.list}>
        {records.map(r => (
          <div key={r.id} className={`${styles.row} ${r.status === 'completed' ? styles.rowDone : styles.rowFailed}`}>
            <div className={styles.rowIcon}>
              {r.status === 'completed'
                ? <CheckCircle size={16} className={styles.iconDone} />
                : <XCircle size={16} className={styles.iconFail} />}
            </div>
            <div className={styles.rowBody}>
              <span className={styles.rowTitle}>{r.title || r.url || 'Untitled'}</span>
              <div className={styles.rowMeta}>
                {r.quality && <span className={styles.chip}>{r.quality}</span>}
                {r.file_size && <span className={styles.chip}>{fmtSize(r.file_size)}</span>}
                <span className={styles.chip}>{fmtDateTime(r.created_at)}</span>
              </div>
              {r.status === 'failed' && r.error_msg && (
                <p className={styles.errMsg}>{r.error_msg}</p>
              )}
              {r.status === 'completed' && r.file_path && (
                <p className={styles.path}>{r.file_path}</p>
              )}
            </div>
            {onReAnalyze && r.url && (
              <button
                className={styles.reAnalyzeBtn}
                onClick={() => onReAnalyze(r.url)}
                title="Analyze this URL again"
              >
                <RotateCcw size={14} />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

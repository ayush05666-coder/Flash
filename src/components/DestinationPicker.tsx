import { FolderOpen } from 'lucide-react'
import styles from './DestinationPicker.module.css'

interface Props {
  value: string
  onChange: (v: string) => void
  disabled?: boolean
}

export default function DestinationPicker({ value, onChange, disabled }: Props) {
  return (
    <div className={styles.wrap}>
      <label className={styles.label}>
        <FolderOpen size={14} />
        Save To
      </label>
      <div className={styles.inputRow}>
        <input
          className={styles.input}
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="~/Downloads"
          disabled={disabled}
          spellCheck={false}
        />
        <span className={styles.note}>
          Enter the path on your local machine where Flash Media (desktop) will save the file.
        </span>
      </div>
    </div>
  )
}

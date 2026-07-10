import styles from './Header.module.css'

export default function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.logoRow}>
        <span className={styles.bolt}>
          <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor">
            <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
          </svg>
        </span>
        <span className={styles.name}>FLASH MEDIA</span>
      </div>
      <p className={styles.sub}>Download video &amp; audio from thousands of sites</p>
    </header>
  )
}

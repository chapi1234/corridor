import { BookOpen, Moon, Sun } from 'lucide-react'

import { useAppStore } from '@/state/store'
import { Button, IconButton } from '@/ui/Button'

import styles from './Header.module.css'

function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden className={styles.mark}>
      {/* A road vanishing to the horizon, its centre line as a risk scale. */}
      <path d="M12 2h8l10 28H2L12 2Z" className={styles.road} />
      <path d="M16 6v3" stroke="var(--risk-0)" />
      <path d="M16 12v4" stroke="var(--risk-1)" />
      <path d="M16 19v4" stroke="var(--risk-2)" />
      <path d="M16 26v4" stroke="var(--risk-3)" />
    </svg>
  )
}

export function Header() {
  const theme = useAppStore((s) => s.theme)
  const setTheme = useAppStore((s) => s.setTheme)
  const setRulesOpen = useAppStore((s) => s.setRulesOpen)
  const source = useAppStore((s) => s.plan?.meta.routing_source)

  return (
    <header className={styles.header}>
      <a className={styles.brand} href="/" aria-label="Corridor home">
        <Logo />
        <span className={styles.wordmark}>Corridor</span>
        <span className={styles.tagline}>Weather-aware truck routing</span>
      </a>
      <div className={styles.actions}>
        {source && (
          <span className={styles.source} title={`Routing: ${source}`}>
            {source.split(' (')[0]}
          </span>
        )}
        <Button
          variant="ghost"
          size="sm"
          icon={<BookOpen size={14} />}
          onClick={() => setRulesOpen(true)}
        >
          Rules
        </Button>
        <IconButton
          variant="ghost"
          label={theme === 'night' ? 'Switch to day theme' : 'Switch to night theme'}
          icon={theme === 'night' ? <Sun size={16} /> : <Moon size={16} />}
          onClick={() => setTheme(theme === 'night' ? 'day' : 'night')}
        />
      </div>
    </header>
  )
}

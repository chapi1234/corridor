import { Check, Link2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/ui/Button'

const CONFIRM_MS = 2000

/** Copies the current URL, which names the plan snapshot (`p=`) and the trip inputs. */
export function ShareButton() {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), CONFIRM_MS)
    return () => window.clearTimeout(id)
  }, [copied])

  const copy = () => {
    void navigator.clipboard
      ?.writeText(window.location.href)
      .then(() => setCopied(true))
      .catch(() => undefined)
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      icon={copied ? <Check size={14} /> : <Link2 size={14} />}
      onClick={copy}
      aria-live="polite"
    >
      {copied ? 'Copied' : 'Share'}
    </Button>
  )
}

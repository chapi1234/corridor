import type { ButtonHTMLAttributes, ReactNode } from 'react'

import styles from './Button.module.css'

type Variant = 'primary' | 'ghost' | 'subtle'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md' | 'lg'
  icon?: ReactNode
}

export function Button({
  variant = 'subtle',
  size = 'md',
  icon,
  className,
  children,
  ...rest
}: ButtonProps) {
  const classes = [styles.button, styles[variant], styles[size], className]
    .filter(Boolean)
    .join(' ')
  return (
    <button type="button" className={classes} {...rest}>
      {icon}
      {children}
    </button>
  )
}

export function IconButton({ label, ...rest }: ButtonProps & { label: string }) {
  return <Button aria-label={label} title={label} className={styles.iconOnly} {...rest} />
}

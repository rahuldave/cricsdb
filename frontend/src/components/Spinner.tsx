/**
 * The spinning circle shown while data loads.
 * @packageDocumentation
 */
/** Props of `Spinner`. */
interface SpinnerProps {
  label?: string // text shown next to the spinner and read by screen readers; "Loading" for screen readers when absent
  size?: 'sm' | 'md' | 'lg' // the circle's size; defaults to md
}

const SIZE_CLASSES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-[3px]',
}

/** Show a centred spinner, with an optional label beside it. */
export default function Spinner({ label, size = 'md' }: SpinnerProps) {
  return (
    <div className="flex items-center justify-center gap-3 py-8 wisden-spinner-wrap">
      <span
        className={`inline-block rounded-full wisden-spinner ${SIZE_CLASSES[size]}`}
        role="status"
        aria-label={label || 'Loading'}
      />
      {label && <span className="text-sm">{label}</span>}
    </div>
  )
}

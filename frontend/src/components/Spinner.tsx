interface SpinnerProps {
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

const SIZE_CLASSES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-[3px]',
}

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

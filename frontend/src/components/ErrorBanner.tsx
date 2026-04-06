interface ErrorBannerProps {
  message: string
  onRetry?: () => void
}

export default function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      <span className="flex-shrink-0 mt-0.5 font-bold">!</span>
      <div className="flex-1">
        <div className="font-medium">Something went wrong</div>
        <div className="text-red-700 mt-0.5">{message}</div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex-shrink-0 rounded border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
        >
          Retry
        </button>
      )}
    </div>
  )
}

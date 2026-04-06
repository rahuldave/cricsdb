interface ErrorBannerProps {
  message: string
  onRetry?: () => void
}

export default function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div role="alert" className="wisden-errorbanner">
      <div className="wisden-errorbanner-mark">!</div>
      <div className="wisden-errorbanner-body">
        <div className="wisden-errorbanner-title">Something went wrong</div>
        <div className="wisden-errorbanner-msg">{message}</div>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="wisden-errorbanner-retry">
          Retry
        </button>
      )}
    </div>
  )
}

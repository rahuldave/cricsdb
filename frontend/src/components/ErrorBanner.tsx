/**
 * The red error box that a page shows when a request fails.
 * @packageDocumentation
 */

/** Props of `ErrorBanner`. */
interface ErrorBannerProps {
  message: string // the error text to show
  onRetry?: () => void // called by the Retry button; no button when absent
}

/** Show an error message in a red box, with a Retry button when `onRetry` is given. */
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

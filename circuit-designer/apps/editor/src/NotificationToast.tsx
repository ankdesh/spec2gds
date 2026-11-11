import { useEffect, useRef, useState } from "react";

export function NotificationToast({ message, onDismiss, onDetails }: {
  message: string;
  onDismiss(): void;
  onDetails?: () => void;
}) {
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const remaining = useRef(5000);
  const dismiss = useRef(onDismiss);
  dismiss.current = onDismiss;
  useEffect(() => {
    if (hover || focus) return;
    const start = Date.now();
    const timer = window.setTimeout(() => dismiss.current(), remaining.current);
    return () => { window.clearTimeout(timer); remaining.current = Math.max(0, remaining.current - (Date.now() - start)); };
  }, [hover, focus]);
  return <div className="app-toast" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
    onFocus={() => setFocus(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocus(false); }}>
    <span role="status" aria-live="polite">{message}</span>
    {onDetails && <button type="button" onClick={onDetails}>View details</button>}
    <button type="button" aria-label="Dismiss notification" onClick={onDismiss}>×</button>
  </div>;
}

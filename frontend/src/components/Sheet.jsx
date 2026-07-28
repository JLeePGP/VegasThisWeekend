import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

/** Bottom sheet: backdrop, escape to close, and the page behind held still. */
export default function Sheet({ open, onClose, labelledBy, children }) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const handleKey = (keyEvent) => {
      if (keyEvent.key === 'Escape') {
        keyEvent.stopPropagation();
        onClose();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleKey);
    panelRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div
        ref={panelRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
      >
        <div className="sheet__grip" />
        {children}
      </div>
    </>,
    document.body,
  );
}

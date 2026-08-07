import { useEffect, useId, useRef, useState } from 'react';
import { IconChevronDown } from './Icons';

// A labelled dropdown for the desktop filter bar.
//
// Deliberately not built on `Sheet`. A sheet locks body scroll and covers the screen,
// which is right for a modal on a phone and wrong here — these panels are small, the page
// behind them stays readable, and locking the scroll of a document that now actually
// scrolls would be a visible jolt every time one opened.
//
// No portal either. The panel is absolutely positioned inside its own wrapper, which
// works because the desktop shell has no clipping ancestor — `.app` and `.screen` both
// drop their `overflow` at this breakpoint. That trade is worth naming: a portal would
// survive a future ancestor growing an `overflow: hidden`, but it would also need
// positioning maths and a scroll listener to keep the panel glued to its trigger.
export default function Popover({ label, badge = 0, children }) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return undefined;

    const handleKey = (keyEvent) => {
      if (keyEvent.key === 'Escape') {
        keyEvent.stopPropagation();
        setOpen(false);
      }
    };

    // `pointerdown` rather than `click`, so the panel is already closed by the time a
    // click lands on whatever was underneath it. On `click` the panel would still be open
    // during the press and would swallow the first interaction outside itself.
    const handleOutside = (pointerEvent) => {
      if (!wrapper.current?.contains(pointerEvent.target)) setOpen(false);
    };

    document.addEventListener('keydown', handleKey);
    document.addEventListener('pointerdown', handleOutside);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('pointerdown', handleOutside);
    };
  }, [open]);

  return (
    <div className="popover" ref={wrapper}>
      <button
        type="button"
        className="filter-trigger"
        data-active={badge > 0}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        {label}
        {badge > 0 && <span className="filter-trigger__count">{badge}</span>}
        <IconChevronDown className="popover__chevron" width={16} height={16} />
      </button>

      {open && (
        <div className="popover__panel" id={panelId}>
          {children}
        </div>
      )}
    </div>
  );
}

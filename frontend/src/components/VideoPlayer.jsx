import { useEffect, useRef } from 'react';
import { IconClose } from './Icons';

// Full-screen video, at whatever shape the video actually is.
//
// The rule this component exists to keep: event video is shot vertically, for phones, at
// 9:16. Every previous attempt to fit it into the app's own layout cropped it, faded it,
// or put it behind text — and a cropped 9:16 clip loses the top and bottom of the frame,
// which in a venue clip is usually the performer and the crowd. So it plays over
// everything, `object-fit: contain`, on black, and closes back to the detail view.
//
// Opened only from a deliberate tap on the play button, which is also what makes sound
// allowed: autoplay policies block audio without a user gesture, and there is one here.

export default function VideoPlayer({ src, poster, onClose }) {
  const videoRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    // Focus moves into the overlay so Escape and Tab belong to it, and so a screen
    // reader lands here rather than continuing down the page behind it.
    closeRef.current?.focus();

    const onKeyDown = (keyEvent) => {
      if (keyEvent.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);

    // The page behind must not scroll under the overlay on touch.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  useEffect(() => {
    // Rejection is not a failure worth reporting: the controls are right there, so a
    // blocked autoplay leaves a paused video with a play button on it.
    videoRef.current?.play().catch(() => {});
  }, [src]);

  return (
    <div
      className="player"
      role="dialog"
      aria-modal="true"
      aria-label="Event video"
      // Tapping the surround closes, the way every full-screen media viewer behaves.
      // Guarded on the target so a tap that lands on the video itself does not.
      onClick={(clickEvent) => {
        if (clickEvent.target === clickEvent.currentTarget) onClose();
      }}
    >
      <video
        ref={videoRef}
        className="player__video"
        src={src}
        poster={poster ?? undefined}
        controls
        playsInline
        loop
        preload="metadata"
      />

      <button
        ref={closeRef}
        type="button"
        className="player__close"
        onClick={onClose}
        aria-label="Close video"
      >
        <IconClose width={20} height={20} />
      </button>
    </div>
  );
}

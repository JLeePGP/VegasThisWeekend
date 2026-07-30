import { useEffect, useRef, useState } from 'react';
import { vibeLabel } from '../constants';

// The media layer behind a card: a video if the event has one, otherwise an image,
// otherwise a poster generated from the event's own id. Now that media fills the whole
// screen, the generated fallback is a real design surface rather than a placeholder —
// it is what most events will show until every one has artwork.

function hashOf(text) {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

/**
 * @param {boolean} active  True only for the card on top of the stack. Video plays only
 *   when active: three cards autoplaying at once burns battery and, on iOS, competes for
 *   the single decode pipeline and ends up playing none of them.
 */
export default function Poster({ event, compact = false, active = true }) {
  // Media that stops resolving must degrade to the next option rather than showing a
  // broken-image icon. Venue and ticketing URLs die without warning — which is the whole
  // argument for mirroring to R2.
  const [imageFailed, setImageFailed] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => setImageFailed(false), [event.image_url]);
  useEffect(() => setVideoFailed(false), [event.video_url]);

  const showVideo = Boolean(event.video_url) && !videoFailed && !compact;
  const showImage = !showVideo && Boolean(event.image_url) && !imageFailed;

  useEffect(() => {
    const element = videoRef.current;
    if (!element) return;

    if (active) {
      // play() rejects on its own if autoplay is blocked (a muted inline video normally
      // is not, but a data-saver setting can still refuse). The poster frame stays up,
      // so a rejection is a silent downgrade rather than a failure.
      element.play().catch(() => {});
    } else {
      element.pause();
    }
  }, [active, showVideo]);

  if (showVideo) {
    return (
      <div className="poster">
        <video
          ref={videoRef}
          className="poster__video"
          src={event.video_url}
          // All four are required together for inline autoplay on iOS: drop `muted` or
          // `playsInline` and Safari opens the fullscreen player instead.
          muted
          playsInline
          loop
          autoPlay
          preload="metadata"
          poster={event.image_url ?? undefined}
          onError={() => setVideoFailed(true)}
          tabIndex={-1}
          aria-hidden="true"
        />
      </div>
    );
  }

  if (showImage) {
    return (
      <div className="poster">
        <img
          className="poster__img"
          src={event.image_url}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setImageFailed(true)}
        />
      </div>
    );
  }

  const seed = hashOf(event.id ?? event.name ?? '');
  const word = vibeLabel(event.vibe);

  return (
    <div
      className="poster poster--generated"
      aria-hidden="true"
      style={{
        '--poster-1': `var(--vibe-${event.vibe}-1, var(--ink-700))`,
        '--poster-2': `var(--vibe-${event.vibe}-2, var(--ink-850))`,
        '--poster-angle': `${115 + (seed % 70)}deg`,
        '--poster-x': `${18 + (seed % 6) * 11}%`,
        '--poster-band': `${-24 + (seed % 5) * 12}deg`,
      }}
    >
      <div className="poster__glow" />
      <div className="poster__bands" />
      {/* A huge, near-invisible word bleeding off the edge gives the empty middle of a
          full-height card something to hold, without competing with the title. It
          replaces the small outlined word that used to sit top-left — now that the
          filter bar floats over the card, that corner is no longer the card's to use. */}
      {!compact && <span className="poster__ghost">{word}</span>}
      <div className="poster__grain" />
    </div>
  );
}

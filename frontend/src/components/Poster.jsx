import { useEffect, useState } from 'react';
import { vibeLabel } from '../constants';

// An event's still image: the mirrored photo if it has one, otherwise a poster generated
// from the event's own id. Most events will show the generated one until every one has
// artwork, so it is a real design surface rather than a placeholder.
//
// This used to render video too, autoplaying behind the top card. It does not any more,
// and that is the point rather than an omission: an event's video plays at its own 9:16
// shape from the detail view's play button, never cropped into a rectangle it does not
// fit, never as motion behind text, and never in a list row.

function hashOf(text) {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

/**
 * @param {boolean} compact  Thumbnail size — drops the decoration that only reads large.
 */
export default function Poster({ event, compact = false }) {
  // An image that stops resolving degrades to the generated poster rather than a broken
  // -image icon. Venue and ticketing URLs die without warning, which is the whole
  // argument for mirroring to R2.
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => setImageFailed(false), [event.image_url]);

  if (event.image_url && !imageFailed) {
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
      {/* A huge, near-invisible word bleeding off the edge gives a large poster something
          to hold without competing with the title. Pointless at thumbnail size. */}
      {!compact && <span className="poster__ghost">{word}</span>}
      <div className="poster__grain" />
    </div>
  );
}

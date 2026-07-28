import { useEffect, useState } from 'react';
import { vibeLabel } from '../constants';

// Sample events carry no image, and real ones will not always have a good one either.
// Rather than a grey box, each event gets a poster generated from its own id: the colours
// come from its category, the composition from a hash, so it is stable across renders and
// distinct from its neighbours in the stack.

function hashOf(text) {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

export default function Poster({ event, compact = false }) {
  // An image URL that stops resolving must degrade to the generated poster rather than
  // a broken-image icon. Real events point at R2, but an unmirrored venue URL can die
  // at any time — which is the entire reason R2 exists.
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

  return (
    <div
      className="poster"
      aria-hidden="true"
      style={{
        '--poster-1': `var(--vibe-${event.vibe}-1, var(--ink-700))`,
        '--poster-2': `var(--vibe-${event.vibe}-2, var(--ink-850))`,
        '--poster-angle': `${115 + (seed % 70)}deg`,
        '--poster-x': `${18 + (seed % 6) * 11}%`,
      }}
    >
      <div className="poster__glow" />
      {!compact && <span className="poster__word">{vibeLabel(event.vibe)}</span>}
      <div className="poster__grain" />
    </div>
  );
}

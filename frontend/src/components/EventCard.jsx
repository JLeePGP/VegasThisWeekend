import { priceLabel, vibeLabel } from '../constants';
import { whenLabel } from '../format';
import { IconChevronUp } from './Icons';
import Poster from './Poster';

const clamp01 = (value) => Math.min(1, Math.max(0, value));

/**
 * The swipe card face.
 *
 * `intent` runs -1 (fully dragged toward skip) to 1 (fully dragged toward save) and only
 * drives the verdict stamps — the transform itself belongs to the stack.
 */
export default function EventCard({ event, intent = 0, onExpand }) {
  return (
    <article className="card">
      <div className="card__poster">
        <Poster event={event} />

        <div className="card__chips">
          <span className="card__chip">{vibeLabel(event.vibe)}</span>
          <span className="card__chip card__chip--price">{priceLabel(event.price_tier)}</span>
        </div>

        <span className="card__verdict card__verdict--save" style={{ opacity: clamp01(intent) }}>
          Save
        </span>
        <span className="card__verdict card__verdict--skip" style={{ opacity: clamp01(-intent) }}>
          Skip
        </span>

        <div className="card__meta">
          <span className="card__when">{whenLabel(event.start_at)}</span>
          <h2 className="card__title">{event.name}</h2>
          <p className="card__venue">
            {event.venue} · {event.neighborhood}
          </p>
        </div>
      </div>

      <div className="card__body">
        <p className="card__hook">{event.hook}</p>
        <button
          type="button"
          className="card__expand"
          onClick={onExpand}
          aria-label={`Details for ${event.name}`}
        >
          <IconChevronUp width={18} height={18} />
        </button>
      </div>
    </article>
  );
}

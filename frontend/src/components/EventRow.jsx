import { Link } from 'react-router-dom';
import { priceLabel } from '../constants';
import { hasFinished, timeLabel, whenLabel } from '../format';
import { IconSave, IconTrash } from './Icons';
import Poster from './Poster';

// One row shape for every list in the app — the day-grouped listing, Saved, and a shared
// list. They were three components with three slightly different ideas of what a row
// says; the differences were accidents rather than decisions.
//
// What a row deliberately does not carry: a hook line, and the venue. The hook made rows
// read like every other event site, and the curation here lives in *which* events are
// listed rather than in a line of copy about each one. Venue belongs on the detail view,
// where there is room for the address and a map link next to it.

/**
 * @param {boolean} withDay  Show the day as well as the time. The listing groups by day
 *   under a header, so a row there needs only the time; Saved and shared lists are one
 *   flat run across several days and would be ambiguous without it.
 */
export default function EventRow({ event, withDay = false, onSave, isSaved = false, onRemove }) {
  const finished = hasFinished(event.end_at);

  return (
    <li className="row">
      {/* The whole row is one link, so the tap target is the row and not just the title.
          A Link rather than a click handler: it is a real navigation, which means
          middle-click, long-press and "open in new tab" all behave. The event travels in
          router state so arriving from a list needs no second fetch — the detail screen
          falls back to fetching by id when someone lands on the URL directly. */}
      <Link className="row__main" to={`/e/${event.id}`} state={{ event }}>
        <span className="row__poster" aria-hidden="true">
          <Poster event={event} compact />
        </span>

        <span className="row__text">
          <span className="row__when">{withDay ? whenLabel(event.start_at) : timeLabel(event.start_at)}</span>
          <span className="row__title">{event.name}</span>
          <span className="row__meta">
            {event.neighborhood}
            <span className="row__price">{event.price_note || priceLabel(event.price_tier)}</span>
          </span>
          {finished && <span className="row__past">Already happened</span>}
        </span>
      </Link>

      {/* Outside the link, or a save would navigate. Saving is the one thing that
          survived the swipe deck, and it stays one tap from the list. */}
      {onSave && (
        <button
          type="button"
          className={isSaved ? 'row__save is-saved' : 'row__save'}
          onClick={() => onSave(event)}
          aria-pressed={isSaved}
          aria-label={isSaved ? `Saved: ${event.name}` : `Save ${event.name}`}
        >
          <IconSave width={19} height={19} />
        </button>
      )}

      {onRemove && (
        <button
          type="button"
          className="row__remove"
          onClick={() => onRemove(event.id)}
          aria-label={`Remove ${event.name}`}
        >
          <IconTrash width={17} height={17} />
        </button>
      )}
    </li>
  );
}

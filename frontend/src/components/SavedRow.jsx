import { hasFinished, whenLabel } from '../format';
import { IconTrash } from './Icons';
import Poster from './Poster';

export default function SavedRow({ event, onOpen, onRemove }) {
  const finished = hasFinished(event.end_at);

  return (
    <li className="saved-row">
      <div className="saved-row__poster" aria-hidden="true">
        <Poster event={event} compact />
      </div>

      {/* One button around the text rather than a click handler on a div, so the row is
          reachable by keyboard and announced as actionable. */}
      <button
        type="button"
        className="saved-row__main"
        onClick={() => onOpen(event)}
        aria-label={`Details for ${event.name}`}
      >
        <span className="saved-row__when">{whenLabel(event.start_at)}</span>
        <span className="saved-row__title">{event.name}</span>
        <span className="saved-row__venue">
          {event.venue} · {event.neighborhood}
        </span>
        {finished && <span className="saved-row__past">Already happened</span>}
      </button>

      {onRemove && (
        <button
          type="button"
          className="saved-row__remove"
          onClick={() => onRemove(event.id)}
          aria-label={`Remove ${event.name}`}
        >
          <IconTrash width={17} height={17} />
        </button>
      )}
    </li>
  );
}

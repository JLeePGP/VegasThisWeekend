import { trackTicketClicked } from '../analytics';
import { priceLabel, vibeLabel } from '../constants';
import { whenLabel } from '../format';
import { mapsUrl } from '../maps';
import { IconChevronUp, IconGlobe, IconPin, IconTicket } from './Icons';
import Poster from './Poster';

/**
 * The swipe card face. Media fills the card edge to edge and every control floats over
 * it, so the layout is one stacking context rather than a poster above a text panel.
 *
 * The verdict stamps deliberately live in the stack, not here — see SwipeStack.
 */
export default function EventCard({ event, isTop = true, onExpand }) {
  // Not every event sells tickets — a free dog-park happy hour showing a Tickets button
  // is a small lie. Each link renders only when the event actually has one.
  const hasTickets = Boolean(event.ticket_url);
  const hasWebsite = Boolean(event.source_url);

  return (
    <article className="card">
      <Poster event={event} active={isTop} />
      <div className="card__scrim" />

      <div className="card__meta">
        {/* Category and price sit with the title rather than floating at the top of the
            card: up there they collided with the filter bar, and the collision moved
            depending on whether the sample-data banner was showing. */}
        <div className="card__chips">
          <span className="card__chip">{vibeLabel(event.vibe)}</span>
          <span className="card__chip card__chip--price">{priceLabel(event.price_tier)}</span>
        </div>

        <span className="card__when">{whenLabel(event.start_at)}</span>
        <h2 className="card__title">{event.name}</h2>
        {/* Venue and neighbourhood stay the label even once an address exists: a street
            number is not what someone recognises at a glance. The address is what the
            Map link resolves against. */}
        <p className="card__venue">
          {event.venue} · {event.neighborhood}
        </p>
        <p className="card__hook">{event.hook}</p>

        <div className="card__links">
          {hasTickets && (
            <a
              className="cardlink cardlink--primary"
              href={event.ticket_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackTicketClicked({ vibe: event.vibe })}
            >
              <IconTicket width={16} height={16} />
              Tickets
            </a>
          )}
          {hasWebsite && (
            <a
              className="cardlink"
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <IconGlobe width={16} height={16} />
              Website
            </a>
          )}
          <a
            className="cardlink"
            href={mapsUrl(event)}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Map for ${event.venue}`}
          >
            <IconPin width={16} height={16} />
            Map
          </a>
          <button
            type="button"
            className="cardlink cardlink--details"
            onClick={onExpand}
            aria-label={`Details for ${event.name}`}
          >
            <IconChevronUp width={16} height={16} />
            Details
          </button>
        </div>
      </div>
    </article>
  );
}

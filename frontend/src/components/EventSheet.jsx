import { useEffect, useState } from 'react';
import { trackSave, trackTicketClick, trackTipReveal, trackWebsiteClick } from '../analytics';
import { priceLabel, vibeLabel } from '../constants';
import { fullDateLabel, rangeLabel } from '../format';
import { mapsUrl } from '../maps';
import {
  IconChevronDown,
  IconClose,
  IconGlobe,
  IconPin,
  IconSave,
  IconTicket,
  IconTip,
} from './Icons';
import Poster from './Poster';
import Sheet from './Sheet';

export default function EventSheet({ event, open, onClose, onSave, isSaved }) {
  const [tipRevealed, setTipRevealed] = useState(false);

  // Each event's tip starts hidden again — revealing one is a deliberate tap.
  useEffect(() => setTipRevealed(false), [event?.id]);

  if (!event) return null;

  return (
    <Sheet open={open} onClose={onClose} labelledBy="detail-title">
      <div className="sheet__scroll">
        <div className="detail__poster">
          <Poster event={event} />
          <button type="button" className="detail__close" onClick={onClose} aria-label="Close">
            <IconClose width={18} height={18} />
          </button>
        </div>

        <div className="detail__head">
          <h2 className="detail__title" id="detail-title">
            {event.name}
          </h2>

          <dl className="detail__facts">
            <div className="detail__fact">
              <dt>When</dt>
              <dd>
                {fullDateLabel(event.start_at)} · {rangeLabel(event.start_at, event.end_at)}
              </dd>
            </div>
            <div className="detail__fact">
              <dt>Where</dt>
              <dd>
                {event.venue}, {event.neighborhood}
                {event.address && <span className="detail__address">{event.address}</span>}
                <a
                  className="detail__maplink"
                  href={mapsUrl(event)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <IconPin width={14} height={14} />
                  Open in Maps
                </a>
              </dd>
            </div>
            <div className="detail__fact">
              <dt>Price</dt>
              <dd>{event.price_note || priceLabel(event.price_tier)}</dd>
            </div>
            <div className="detail__fact">
              <dt>Category</dt>
              <dd>{vibeLabel(event.vibe)}</dd>
            </div>
          </dl>

          <p className="detail__description">{event.description}</p>

          {/* The card offers this too; without it here, opening the details is a dead end
              for anyone who wants the venue's own page rather than a ticket. */}
          {event.source_url && (
            <a
              className="detail__link"
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackWebsiteClick(event.id)}
            >
              <IconGlobe width={16} height={16} />
              Event website
            </a>
          )}

          {event.insider_tip && (
            <div className="tip">
              <button
                type="button"
                className="tip__toggle"
                aria-expanded={tipRevealed}
                onClick={() => {
                  // Only count the reveal, not the collapse.
                  if (!tipRevealed) trackTipReveal(event.id);
                  setTipRevealed((current) => !current);
                }}
              >
                <IconTip className="tip__icon" width={20} height={20} />
                Insider tip
                <IconChevronDown className="tip__chevron" width={18} height={18} />
              </button>
              {tipRevealed && <p className="tip__body">{event.insider_tip}</p>}
            </div>
          )}
        </div>
      </div>

      <div className="sheet__footer">
        {event.ticket_url && (
          <a
            className="btn btn--secondary"
            href={event.ticket_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackTicketClick(event.id)}
          >
            <IconTicket width={18} height={18} />
            Tickets
          </a>
        )}
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={isSaved}
          onClick={() => {
            trackSave(event.id);
            onSave(event);
            onClose();
          }}
        >
          <IconSave width={18} height={18} />
          {isSaved ? 'Saved' : 'Save'}
        </button>
      </div>
    </Sheet>
  );
}

// A maps link from plain text. No API key, no billing account, no SDK — Google's
// universal search URL takes a query string and resolves it, which is all we need to
// get someone from a card to directions.
//
// Falls back to venue + neighbourhood when an event has no street address, which every
// event created before the address column does. That resolves well enough for a named
// Vegas venue, and is strictly better than offering nothing.

const LOCALITY = 'Las Vegas, NV';

export function locationQuery(event) {
  const address = event.address?.trim();
  if (address) {
    // Only append the city when the address does not already carry it, or the query
    // ends up as "... Las Vegas, NV, Las Vegas, NV".
    return /las vegas/i.test(address) ? address : `${address}, ${LOCALITY}`;
  }
  return [event.venue, event.neighborhood, LOCALITY].filter(Boolean).join(', ');
}

export const mapsUrl = (event) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(locationQuery(event))}`;

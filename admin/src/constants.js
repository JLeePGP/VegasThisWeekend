// Mirrors the backend enums. A mismatch here surfaces as a 422 rather than bad data,
// but keeping them in step avoids the round trip.

// "Sober" is deliberately absent: it is an attribute (alcohol_free), not a category.
// See the note on the backend Vibe enum for why adding it here would break the filter.
export const VIBES = [
  { value: 'nightlife', label: 'Nightlife' },
  { value: 'food_drink', label: 'Food & Drink' },
  { value: 'music', label: 'Music' },
  { value: 'shows', label: 'Shows' },
  { value: 'sports', label: 'Sports' },
  { value: 'outdoors', label: 'Outdoors' },
  { value: 'fitness', label: 'Fitness' },
  { value: 'family', label: 'Family' },
  { value: 'adult', label: 'Adult' },
  { value: 'local', label: 'Local' },
];

export const PRICE_TIERS = [
  { value: 'free', label: 'Free' },
  { value: 'budget', label: '$ — under $50' },
  { value: 'moderate', label: '$$ — $50 to $150' },
  { value: 'premium', label: '$$$ — $150+' },
];

export const NEIGHBORHOODS = [
  'The Strip',
  'Off-Strip',
  'Downtown',
  'Arts District',
  'Chinatown',
  'Summerlin',
  'Henderson',
  'East Side',
  'West Side',
  'North Las Vegas',
  'Southwest',
  'Red Rock',
  'Elsewhere',
];

export const WEEKDAYS = [
  { value: 'monday', short: 'Mon' },
  { value: 'tuesday', short: 'Tue' },
  { value: 'wednesday', short: 'Wed' },
  { value: 'thursday', short: 'Thu' },
  { value: 'friday', short: 'Fri' },
  { value: 'saturday', short: 'Sat' },
  { value: 'sunday', short: 'Sun' },
];

export const HOOK_MAX = 160;

/** An empty event form. Times use the exact format `datetime-local` inputs produce. */
export const EMPTY_EVENT = {
  name: '',
  venue: '',
  neighborhood: 'The Strip',
  address: '',
  starts_at_local: '',
  ends_at_local: '',
  vibe: 'nightlife',
  // Additional categories beyond the primary. The server drops the primary if it
  // appears here, so there is no need to keep the two in step by hand.
  tags: [],
  alcohol_free: false,
  price_tier: 'moderate',
  price_note: '',
  hook: '',
  description: '',
  image_url: '',
  video_url: '',
  ticket_url: '',
  source_url: '',
  is_active: true,
  mirror_image: true,
};

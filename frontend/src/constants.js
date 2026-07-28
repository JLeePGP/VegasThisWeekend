// Filter vocabularies. These values must stay in step with the backend enums — anything
// else is rejected with a 422 rather than silently ignored.

export const DATE_OPTIONS = [
  { value: 'today', label: 'Today' },
  { value: 'weekend', label: 'This Weekend' },
  { value: 'all', label: 'Anytime' },
];

export const VIBE_OPTIONS = [
  { value: 'nightlife', label: 'Nightlife' },
  { value: 'food_drink', label: 'Food & Drink' },
  { value: 'music', label: 'Music' },
  { value: 'shows', label: 'Shows' },
  { value: 'sports', label: 'Sports' },
  { value: 'outdoors', label: 'Outdoors' },
  { value: 'family', label: 'Family' },
  { value: 'adult', label: 'Adult' },
  { value: 'local', label: 'Local' },
];

// `aria` spells out what the dollar signs mean — "$$" read aloud is meaningless.
export const PRICE_OPTIONS = [
  { value: 'free', label: 'Free', hint: '', aria: 'Free' },
  { value: 'budget', label: '$', hint: 'Under $50', aria: 'Budget, under $50' },
  { value: 'moderate', label: '$$', hint: '$50–150', aria: 'Moderate, $50 to $150' },
  { value: 'premium', label: '$$$', hint: '$150+', aria: 'Premium, $150 and up' },
];

const VIBE_LABELS = Object.fromEntries(VIBE_OPTIONS.map((o) => [o.value, o.label]));
const PRICE_LABELS = Object.fromEntries(PRICE_OPTIONS.map((o) => [o.value, o.label]));

export const vibeLabel = (value) => VIBE_LABELS[value] ?? value;
export const priceLabel = (value) => PRICE_LABELS[value] ?? value;

export const DEFAULT_FILTERS = { date: 'weekend', vibes: [], prices: [] };

// Matches the backend's MAX_SHARE_EVENTS.
export const MAX_SHARE_EVENTS = 20;

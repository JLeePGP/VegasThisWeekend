import { DATE_OPTIONS, PRICE_OPTIONS, VIBE_OPTIONS } from '../constants';
import Popover from './Popover';

// The same four filter groups as the phone, laid out along one horizontal row.
//
// The phone hides vibe and price behind a single sliders button because there is no room
// for fifteen controls on a 390px screen. There is room here, so they come out from
// behind the button and become labelled dropdowns — the filters end up *more* visible on
// desktop than on mobile, not less. Flat chip rows were the other option and would have
// been a fifteen-control wall across the top of the page.

function toggle(list, value) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export default function FilterBarDesktop({ filters, onChange }) {
  const activeCount = filters.vibes.length + filters.prices.length + (filters.alcoholFree ? 1 : 0);

  return (
    <div className="filterbar filterbar--desktop">
      <div className="segmented" role="group" aria-label="When">
        {DATE_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className="segmented__option"
            aria-pressed={filters.date === option.value}
            onClick={() => onChange({ ...filters, date: option.value })}
          >
            {option.label}
          </button>
        ))}
      </div>

      <Popover label="Vibe" badge={filters.vibes.length}>
        <div className="chip-grid">
          {VIBE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className="chip"
              aria-pressed={filters.vibes.includes(option.value)}
              onClick={() => onChange({ ...filters, vibes: toggle(filters.vibes, option.value) })}
            >
              {option.label}
            </button>
          ))}
        </div>
      </Popover>

      <Popover label="Price" badge={filters.prices.length}>
        <div className="chip-grid">
          {PRICE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className="chip"
              aria-label={option.aria}
              aria-pressed={filters.prices.includes(option.value)}
              onClick={() => onChange({ ...filters, prices: toggle(filters.prices, option.value) })}
            >
              {option.label}
              {option.hint && <span className="chip__hint">{option.hint}</span>}
            </button>
          ))}
        </div>
      </Popover>

      {/* Outside the two dropdowns, exactly as it sits outside the vibe chips on the
          phone. It ANDs with everything else where the chips OR with each other, and
          putting it inside the Vibe panel would read as an eleventh category — at which
          point Nightlife + Sober would return every bar in town. */}
      <button
        type="button"
        className="switch switch--inline"
        role="switch"
        aria-checked={filters.alcoholFree}
        onClick={() => onChange({ ...filters, alcoholFree: !filters.alcoholFree })}
      >
        <span className="switch__track" aria-hidden="true">
          <span className="switch__thumb" />
        </span>
        Alcohol-free
      </button>

      {activeCount > 0 && (
        <button
          type="button"
          className="filterbar__clear"
          onClick={() => onChange({ ...filters, vibes: [], prices: [], alcoholFree: false })}
        >
          Clear all
        </button>
      )}
    </div>
  );
}

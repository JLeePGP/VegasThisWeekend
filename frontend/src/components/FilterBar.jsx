import { useState } from 'react';
import { DATE_OPTIONS, PRICE_OPTIONS, VIBE_OPTIONS } from '../constants';
import { IconSliders } from './Icons';
import Sheet from './Sheet';

// One sticky row. Date is the filter people change most, so it stays a single tap;
// vibe and price sit one tap deeper rather than forcing the row to scroll sideways.

function toggle(list, value) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export default function FilterBar({ filters, onChange }) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const activeCount = filters.vibes.length + filters.prices.length;

  return (
    <>
      <div className="filterbar">
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

        <button
          type="button"
          className="filter-trigger"
          data-active={activeCount > 0}
          aria-expanded={sheetOpen}
          onClick={() => setSheetOpen(true)}
        >
          <IconSliders width={18} height={18} />
          <span className="visually-hidden">Vibe and price filters</span>
          {activeCount > 0 && <span className="filter-trigger__count">{activeCount}</span>}
        </button>
      </div>

      <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} labelledBy="filter-sheet-title">
        <h2 className="sheet__title" id="filter-sheet-title">
          Filters
        </h2>

        <div className="sheet__scroll">
          <div className="sheet__pad">
            <div className="sheet__group">
              <span className="sheet__label">Vibe</span>
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
            </div>

            <div className="sheet__group">
              <span className="sheet__label">Price</span>
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
            </div>
          </div>
        </div>

        <div className="sheet__footer">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={activeCount === 0}
            onClick={() => onChange({ ...filters, vibes: [], prices: [] })}
          >
            Clear
          </button>
          <button
            type="button"
            className="btn btn--primary btn--block"
            onClick={() => setSheetOpen(false)}
          >
            Done
          </button>
        </div>
      </Sheet>
    </>
  );
}

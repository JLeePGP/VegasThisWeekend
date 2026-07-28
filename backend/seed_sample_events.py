"""Seed the database with placeholder events for building and testing the swipe UI.

IMPORTANT: every event here is fabricated and every venue name is fictional. Nothing in
this file describes a real Las Vegas event or a real business. Rows are written with
`is_sample=True`, which makes the API report `sample_data: true` and the client show a
"sample data" banner — so placeholder listings cannot be mistaken for real ones.

Replace all of it once the admin panel's URL extraction starts producing real events.

    python seed_sample_events.py           # insert sample rows
    python seed_sample_events.py --reset   # delete existing samples first
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, select

from app.db import Base, SessionLocal, engine
from app.enums import PriceTier, Vibe
from app.models import Event, InsiderTip
from app.timewindow import VEGAS_TZ, now_vegas

# Slots are resolved against the current Vegas date so the seed is always "upcoming",
# whenever it happens to be run.
SLOTS = ("today", "tomorrow", "thu", "fri", "sat", "sun", "next_fri", "next_sat", "next_sun")


@dataclass(frozen=True)
class Sample:
    name: str
    venue: str
    neighborhood: str
    vibe: Vibe
    price_tier: PriceTier
    price_note: str | None
    hook: str
    description: str
    slot: str
    start_hour: int
    duration_hours: float


SAMPLES: tuple[Sample, ...] = (
    # ---------------------------------------------------------------- this weekend
    Sample(
        name="Afterglow: Rooftop Opening Set",
        venue="Solstice Rooftop",
        neighborhood="The Strip",
        vibe=Vibe.NIGHTLIFE,
        price_tier=PriceTier.MODERATE,
        price_note="$60 general admission",
        hook="Sunset sets eleven floors up, before the crowd finds it.",
        description=(
            "An open-air rooftop session that starts while it is still light out and runs "
            "deep into the night. Two rooms, house on the terrace and disco in the lounge, "
            "with the Strip skyline as the backdrop. Arrive early for the golden-hour set."
        ),
        slot="fri",
        start_hour=19,
        duration_hours=6,
    ),
    Sample(
        name="Low Desert Vinyl Night",
        venue="The Gilded Owl",
        neighborhood="Arts District",
        vibe=Vibe.FOOD_DRINK,
        price_tier=PriceTier.FREE,
        price_note="No cover",
        hook="All-vinyl soul and a bartender who actually wants to talk.",
        description=(
            "A small cocktail room that turns the lights down and the records up every "
            "Friday. No cover, no list, no bottle minimum. Expect northern soul, 45s only, "
            "and a short menu of drinks built around mezcal and amaro."
        ),
        slot="fri",
        start_hour=20,
        duration_hours=5,
    ),
    Sample(
        name="Ninth Street Night Market",
        venue="Old Fifth Social Club",
        neighborhood="Downtown",
        vibe=Vibe.LOCAL,
        price_tier=PriceTier.FREE,
        price_note="Free entry, pay per vendor",
        hook="Forty local vendors, zero tourists, one very good tamale cart.",
        description=(
            "A monthly street market run by and for people who actually live here. Local "
            "makers, record diggers, a rotating lineup of food carts, and a beer garden in "
            "the back lot. Cash still moves faster than cards at most stalls."
        ),
        slot="fri",
        start_hour=17,
        duration_hours=5,
    ),
    Sample(
        name="Cactus Sessions: Three-Band Bill",
        venue="The Velvet Cactus",
        neighborhood="Arts District",
        vibe=Vibe.MUSIC,
        price_tier=PriceTier.BUDGET,
        price_note="$18 advance / $22 door",
        hook="Three touring bands, a 200-cap room, and a very loud PA.",
        description=(
            "A tight three-band bill in a room small enough that the drummer can hear you "
            "heckle. Doors at eight, first band at nine, done by one. The green room is a "
            "converted walk-in cooler, which tells you most of what you need to know."
        ),
        slot="fri",
        start_hour=20,
        duration_hours=5,
    ),
    Sample(
        name="Midnight Mass",
        venue="Neon Cathedral",
        neighborhood="The Strip",
        vibe=Vibe.NIGHTLIFE,
        price_tier=PriceTier.PREMIUM,
        price_note="$175 GA / tables from $1,200",
        hook="The big room, the big lights, the big line. Worth it once.",
        description=(
            "The flagship Friday night in a 2,000-capacity room with a resident headliner "
            "and a production budget you can see from the back bar. Doors at ten, headliner "
            "around one. This is the maximalist Vegas nightclub experience, undiluted."
        ),
        slot="fri",
        start_hour=22,
        duration_hours=5,
    ),
    Sample(
        name="The Understudy: Late Show",
        venue="The Understudy",
        neighborhood="Downtown",
        vibe=Vibe.SHOWS,
        price_tier=PriceTier.BUDGET,
        price_note="$30",
        hook="Working comics testing material they are not sure about yet.",
        description=(
            "A ninety-minute late set where touring comedians run unfinished bits in front "
            "of a room that knows the deal. Lineup is announced at the door and never "
            "online. Two-drink minimum, phones in pouches, no exceptions."
        ),
        slot="fri",
        start_hour=22,
        duration_hours=2,
    ),
    Sample(
        name="Red Rock Sunrise Scramble",
        venue="Ironwood Trailhead",
        neighborhood="Red Rock",
        vibe=Vibe.OUTDOORS,
        price_tier=PriceTier.FREE,
        price_note="Free, park entry not included",
        hook="Out and back before the heat turns it into a bad idea.",
        description=(
            "A guided six-mile sunrise hike with about 900 feet of gain, moving at a "
            "conversational pace. Meet at the trailhead lot at five-thirty. Bring two "
            "liters of water minimum. Group turns around by nine regardless of progress."
        ),
        slot="sat",
        start_hour=6,
        duration_hours=3.5,
    ),
    Sample(
        name="Pancakes & Punk Rock Flea",
        venue="Silver Spur Hall",
        neighborhood="North Las Vegas",
        vibe=Vibe.LOCAL,
        price_tier=PriceTier.FREE,
        price_note="Free entry",
        hook="A flea market with a pancake line and a house band.",
        description=(
            "Sixty tables of vintage clothing, tapes, patches, and questionable taxidermy, "
            "plus a pancake breakfast run by the venue's own kitchen and a band playing far "
            "too loud for eleven in the morning. Bring cash and a tote bag."
        ),
        slot="sat",
        start_hour=10,
        duration_hours=5,
    ),
    Sample(
        name="Desert Bloom Family Field Day",
        venue="Desert Bloom Park",
        neighborhood="Summerlin",
        vibe=Vibe.FAMILY,
        price_tier=PriceTier.FREE,
        price_note="Free",
        hook="Shade, sprinklers, and a bouncy castle that has seen things.",
        description=(
            "A morning of low-stakes field games, a splash zone, food trucks, and enough "
            "shade structures to make it survivable. Aimed at ages three to eleven. Parking "
            "fills by nine-thirty, so the overflow lot on the west side is your friend."
        ),
        slot="sat",
        start_hour=9,
        duration_hours=4,
    ),
    Sample(
        name="Copper Lantern Hotpot Crawl",
        venue="Copper Lantern",
        neighborhood="Chinatown",
        vibe=Vibe.FOOD_DRINK,
        price_tier=PriceTier.MODERATE,
        price_note="$75 per person, all-in",
        hook="Four rooms on Spring Mountain in one very committed evening.",
        description=(
            "A guided crawl through four kitchens on the Chinatown corridor, one course "
            "each, ending with hotpot and a round of baijiu that nobody asked for. Capped "
            "at sixteen people. Vegetarian route available if you flag it when booking."
        ),
        slot="sat",
        start_hour=18,
        duration_hours=4,
    ),
    Sample(
        name="Sandstone Summer Series: Headline Night",
        venue="Sandstone Amphitheater",
        neighborhood="Henderson",
        vibe=Vibe.MUSIC,
        price_tier=PriceTier.MODERATE,
        price_note="$95 lawn / $140 reserved",
        hook="Outdoor amphitheater, real sightlines, actual grass.",
        description=(
            "The centrepiece of the outdoor summer run: gates at six, support at seven, "
            "headliner at nine, hard curfew at eleven. Lawn seating is first-come and the "
            "left side gets shade earliest. Sealed water bottles are allowed in."
        ),
        slot="sat",
        start_hour=18,
        duration_hours=5,
    ),
    Sample(
        name="Lumen Room: Illusions in the Round",
        venue="Lumen Room",
        neighborhood="The Strip",
        vibe=Vibe.SHOWS,
        price_tier=PriceTier.MODERATE,
        price_note="$85-$120",
        hook="A close-up magic show where the back row is nine feet away.",
        description=(
            "A theatre-in-the-round built for 140 people and nothing larger. Sleight of "
            "hand, mentalism, and one closing piece that people argue about in the lobby "
            "afterwards. Two shows Saturday; the late one runs looser."
        ),
        slot="sat",
        start_hour=21,
        duration_hours=1.5,
    ),
    Sample(
        name="Little Foxes Basement Party",
        venue="Little Foxes",
        neighborhood="Chinatown",
        vibe=Vibe.NIGHTLIFE,
        price_tier=PriceTier.BUDGET,
        price_note="$20 at the door",
        hook="A hundred-cap basement, one DJ, no photos.",
        description=(
            "Down a staircase behind a noodle shop: a single dark room, a serious sound "
            "system, and a strict no-photos rule that people actually respect. One resident "
            "plays all night. Cash door, no advance tickets, no guest list."
        ),
        slot="sat",
        start_hour=23,
        duration_hours=5,
    ),
    Sample(
        name="Bacchus Hall Burlesque Revue",
        venue="Bacchus Hall",
        neighborhood="Off-Strip",
        vibe=Vibe.ADULT,
        price_tier=PriceTier.MODERATE,
        price_note="$65, 21+",
        hook="Old-school revue, live nine-piece band, genuinely funny host.",
        description=(
            "A classic burlesque revue with live brass instead of backing tracks, a rotating "
            "cast of eight performers, and a compere who carries the room between numbers. "
            "Strictly 21 and over; ID checked at the door."
        ),
        slot="sat",
        start_hour=22,
        duration_hours=2,
    ),
    Sample(
        name="Sunday Session: Sunset Basin FC",
        venue="Sunset Basin Fields",
        neighborhood="Henderson",
        vibe=Vibe.SPORTS,
        price_tier=PriceTier.BUDGET,
        price_note="$25 general admission",
        hook="Lower-league soccer, upper-tier tailgating.",
        description=(
            "A Sunday afternoon home fixture with a supporters' section that takes itself "
            "just seriously enough. Gates two hours before kickoff, grills allowed in the "
            "north lot, and a halftime raffle that funds the youth academy."
        ),
        slot="sun",
        start_hour=16,
        duration_hours=2.5,
    ),
    Sample(
        name="Palm & Pine Long Lunch",
        venue="Palm & Pine",
        neighborhood="Summerlin",
        vibe=Vibe.FOOD_DRINK,
        price_tier=PriceTier.MODERATE,
        price_note="$68 prix fixe",
        hook="A four-hour lunch that ruins the rest of your Sunday, pleasantly.",
        description=(
            "One seating, one menu, four courses, served family-style on a shaded patio. "
            "The kitchen sends what the market gave them that morning, so the menu is only "
            "announced at the table. Wine pairing is optional and generous."
        ),
        slot="sun",
        start_hour=13,
        duration_hours=4,
    ),
    Sample(
        name="Paper Moon Matinee: New Works",
        venue="The Paper Moon",
        neighborhood="Arts District",
        vibe=Vibe.SHOWS,
        price_tier=PriceTier.BUDGET,
        price_note="$22, pay-what-you-can seats available",
        hook="Four short plays, none longer than twenty minutes.",
        description=(
            "A matinee of four new short works from local playwrights, performed by a "
            "rotating company. Runs ninety minutes with one interval. A block of "
            "pay-what-you-can seats is released at the box office an hour before curtain."
        ),
        slot="sun",
        start_hour=14,
        duration_hours=1.75,
    ),
    Sample(
        name="Mesa Verde Golden Hour Ride",
        venue="Mesa Verde Overlook",
        neighborhood="Southwest",
        vibe=Vibe.OUTDOORS,
        price_tier=PriceTier.FREE,
        price_note="Free, bring your own bike",
        hook="Twelve flowy miles timed to end exactly at sunset.",
        description=(
            "A no-drop group ride on smooth intermediate singletrack, leaving with enough "
            "daylight to finish at the overlook for sunset. Front and rear lights required "
            "for the roll-out back to the lot. Hardtails are completely fine."
        ),
        slot="sun",
        start_hour=18,
        duration_hours=2.5,
    ),
    Sample(
        name="Vault Seventeen: Sunday Service",
        venue="Vault Seventeen",
        neighborhood="Downtown",
        vibe=Vibe.NIGHTLIFE,
        price_tier=PriceTier.FREE,
        price_note="Free before 10pm, $15 after",
        hook="The industry night where everyone off shift ends up.",
        description=(
            "Sunday is the real Friday for people who work weekends. Free before ten, "
            "cheap after, and a room that fills with bartenders, dealers, and dancers "
            "coming off shift. Music leans disco and house and never gets aggressive."
        ),
        slot="sun",
        start_hour=21,
        duration_hours=5,
    ),
    # ---------------------------------------------------------------- earlier in the week
    Sample(
        name="Hangar Fight Night: Undercard",
        venue="The Hangar",
        neighborhood="East Side",
        vibe=Vibe.SPORTS,
        price_tier=PriceTier.BUDGET,
        price_note="$40 standing / $70 seated",
        hook="Eight amateur bouts in a converted aircraft hangar.",
        description=(
            "A regional amateur card of eight bouts, run on time, in a hangar with "
            "surprisingly decent acoustics. Standing room wraps the apron and is the best "
            "value in the building. Doors at six, first bell at seven."
        ),
        slot="today",
        start_hour=19,
        duration_hours=3,
    ),
    Sample(
        name="Gilded Owl Industry Tasting",
        venue="The Gilded Owl",
        neighborhood="Arts District",
        vibe=Vibe.FOOD_DRINK,
        price_tier=PriceTier.BUDGET,
        price_note="$35",
        hook="Six pours, one very opinionated distiller.",
        description=(
            "A guided tasting of six agave spirits led by a visiting distiller who does not "
            "hedge. Sixteen seats at the bar, booked in advance. Snacks included, which you "
            "will want by pour four."
        ),
        slot="today",
        start_hour=20,
        duration_hours=2,
    ),
    Sample(
        name="Tuesday Trivia at the Spur",
        venue="Silver Spur Hall",
        neighborhood="North Las Vegas",
        vibe=Vibe.LOCAL,
        price_tier=PriceTier.FREE,
        price_note="Free, teams up to six",
        hook="Genuinely hard trivia and a house team that always wins.",
        description=(
            "Five rounds, no phones, and a quizmaster who writes his own questions and is "
            "smug about it. Teams of up to six. Winners take the bar tab, second place "
            "takes a bag of nickels, which is the actual prize."
        ),
        slot="tomorrow",
        start_hour=19,
        duration_hours=2.5,
    ),
    Sample(
        name="Understudy Open Mic",
        venue="The Understudy",
        neighborhood="Downtown",
        vibe=Vibe.SHOWS,
        price_tier=PriceTier.FREE,
        price_note="Free, sign-up at 7pm",
        hook="Five minutes each, and the light is not a suggestion.",
        description=(
            "Sign-up sheet goes out at seven, first name called at eight, twenty-five slots "
            "and no more. Five minutes each with a hard light. Free to watch, free to try, "
            "brutal either way."
        ),
        slot="tomorrow",
        start_hour=20,
        duration_hours=3,
    ),
    Sample(
        name="Velvet Cactus Songwriter Round",
        venue="The Velvet Cactus",
        neighborhood="Arts District",
        vibe=Vibe.MUSIC,
        price_tier=PriceTier.FREE,
        price_note="Free, tip the players",
        hook="Four writers, four stools, no band, no setlist.",
        description=(
            "Four songwriters trade songs in the round for two hours, explaining where each "
            "one came from between plays. Room stays quiet, which is the whole point. Free "
            "in, and the tip bucket is the entire payment for the night."
        ),
        slot="thu",
        start_hour=20,
        duration_hours=2,
    ),
    Sample(
        name="Neon Cathedral Thursday Preview",
        venue="Neon Cathedral",
        neighborhood="The Strip",
        vibe=Vibe.NIGHTLIFE,
        price_tier=PriceTier.MODERATE,
        price_note="$70 GA",
        hook="Same room as Friday, half the line, most of the lights.",
        description=(
            "The Thursday night run in the main room, with a resident rather than a "
            "headliner. The production is scaled back but the sound system is not, and you "
            "will actually be able to move on the floor."
        ),
        slot="thu",
        start_hour=22,
        duration_hours=5,
    ),
    # ---------------------------------------------------------------- next weekend
    Sample(
        name="Solstice Rooftop: Poolside Day Session",
        venue="Solstice Rooftop",
        neighborhood="The Strip",
        vibe=Vibe.NIGHTLIFE,
        price_tier=PriceTier.PREMIUM,
        price_note="$150 GA / cabanas from $900",
        hook="A daylight party that peaks at three in the afternoon.",
        description=(
            "The Saturday day session: open-air, pool on the deck, and a lineup that runs "
            "noon to seven. Cabanas book out weeks ahead but general admission is usually "
            "available same-day if you arrive before one."
        ),
        slot="next_sat",
        start_hour=12,
        duration_hours=7,
    ),
    Sample(
        name="Sandstone Summer Series: Closing Night",
        venue="Sandstone Amphitheater",
        neighborhood="Henderson",
        vibe=Vibe.MUSIC,
        price_tier=PriceTier.PREMIUM,
        price_note="$160 lawn / $240 reserved",
        hook="The last night of the outdoor run, with three acts.",
        description=(
            "The closing night of the summer series, running three acts instead of two and "
            "pushing curfew to midnight. Expect the lawn to sell out. Rideshare pickup moves "
            "to the south lot for this show only."
        ),
        slot="next_sat",
        start_hour=17,
        duration_hours=7,
    ),
    Sample(
        name="Copper Lantern Dumpling Workshop",
        venue="Copper Lantern",
        neighborhood="Chinatown",
        vibe=Vibe.FAMILY,
        price_tier=PriceTier.BUDGET,
        price_note="$45 adult / $20 child",
        hook="You fold badly for an hour, then eat very well.",
        description=(
            "A hands-on workshop for twelve people at a time, kids welcome and genuinely "
            "catered for. You make four kinds, the kitchen cooks them, and everyone eats "
            "together at the end. Takeaway containers provided, and you will need them."
        ),
        slot="next_sun",
        start_hour=11,
        duration_hours=2.5,
    ),
    Sample(
        name="Paper Moon Late Cabaret",
        venue="The Paper Moon",
        neighborhood="Arts District",
        vibe=Vibe.ADULT,
        price_tier=PriceTier.BUDGET,
        price_note="$35, 21+",
        hook="A cabaret that gets steadily less polite after midnight.",
        description=(
            "A late-night cabaret of music, comedy, and variety acts that runs loose and "
            "occasionally off the rails. Rotating lineup, resident band, 21 and over. The "
            "back two rows are the safest place to sit, relatively speaking."
        ),
        slot="next_fri",
        start_hour=23,
        duration_hours=2.5,
    ),
    Sample(
        name="Ironwood Stargazing Walk",
        venue="Ironwood Trailhead",
        neighborhood="Red Rock",
        vibe=Vibe.OUTDOORS,
        price_tier=PriceTier.FREE,
        price_note="Free, headlamp required",
        hook="Two easy miles out, then everyone turns the lights off.",
        description=(
            "An easy two-mile night walk to a dark clearing where the group kills every "
            "light and an astronomer talks through what is overhead. Red-filter headlamps "
            "strongly preferred. Runs only on nights near the new moon."
        ),
        slot="next_fri",
        start_hour=20,
        duration_hours=3,
    ),
)

# Generic-but-genuine Vegas advice, matched by vibe. Venue-specific tips arrive with real
# events; these exist so the expanded-card tip UI has something to render.
SAMPLE_TIPS: tuple[tuple[str | None, Vibe | None, str, int], ...] = (
    (
        None,
        Vibe.NIGHTLIFE,
        "Guest lists close far earlier than doors do. Getting on one in the afternoon is "
        "usually the difference between walking in and standing in line for ninety minutes.",
        10,
    ),
    (
        None,
        Vibe.OUTDOORS,
        "From May to September, anything strenuous needs to be finished by about 9am. Carry "
        "a litre of water per hour on trail, not per hike.",
        10,
    ),
    (
        None,
        Vibe.FOOD_DRINK,
        "The Chinatown corridor on Spring Mountain Road runs far later than the Strip. Most "
        "kitchens there are still taking orders well after midnight.",
        10,
    ),
    (
        None,
        Vibe.SHOWS,
        "Same-day seats for smaller rooms are usually cheapest at the venue box office, "
        "which skips the per-ticket fees that resale and app listings add on.",
        10,
    ),
    (
        None,
        Vibe.SPORTS,
        "Rideshare surge after a final whistle is brutal. Walking five to ten minutes away "
        "from the venue before requesting a car routinely halves the price.",
        10,
    ),
    (
        None,
        Vibe.LOCAL,
        "Downtown parking is free in several garages off Fremont if you avoid the casino "
        "lots on the main drag. Check signage for validation hours before you leave the car.",
        10,
    ),
    (
        None,
        Vibe.FAMILY,
        "Mornings are the only comfortable window for outdoor family events in summer. Most "
        "shaded park areas fill up within thirty minutes of opening.",
        10,
    ),
    (
        None,
        Vibe.ADULT,
        "21-and-over rooms card at the door every time, with no exceptions for a group. A "
        "physical ID moves faster than a phone wallet at most doors.",
        10,
    ),
    (
        None,
        Vibe.MUSIC,
        "Outdoor amphitheatre shows in summer stay hot well past sunset. Lawn seating on the "
        "east side loses direct sun first.",
        10,
    ),
)


def _weekend_anchor(today: date) -> date:
    """The Friday of the weekend the API would call 'this weekend'."""
    weekday = today.weekday()  # Monday is 0
    if weekday >= 4:  # already Fri/Sat/Sun, so this weekend has started
        return today - timedelta(days=weekday - 4)
    return today + timedelta(days=4 - weekday)


def _resolve_day(slot: str, today: date) -> date:
    friday = _weekend_anchor(today)
    match slot:
        case "today":
            return today
        case "tomorrow":
            return today + timedelta(days=1)
        case "thu":
            return friday - timedelta(days=1)
        case "fri":
            return friday
        case "sat":
            return friday + timedelta(days=1)
        case "sun":
            return friday + timedelta(days=2)
        case "next_fri":
            return friday + timedelta(days=7)
        case "next_sat":
            return friday + timedelta(days=8)
        case "next_sun":
            return friday + timedelta(days=9)
    raise ValueError(f"Unknown slot {slot!r}; expected one of {SLOTS}")


def build_rows(today: date) -> list[Event]:
    rows: list[Event] = []
    for sample in SAMPLES:
        day = _resolve_day(sample.slot, today)
        start = datetime.combine(day, time(hour=sample.start_hour), tzinfo=VEGAS_TZ)
        end = start + timedelta(hours=sample.duration_hours)
        rows.append(
            Event(
                name=sample.name,
                venue=sample.venue,
                neighborhood=sample.neighborhood,
                start_at=start,
                end_at=end,
                vibe=sample.vibe.value,
                price_tier=sample.price_tier.value,
                price_note=sample.price_note,
                hook=sample.hook,
                description=sample.description,
                # No image: the client renders a generated poster. Real events will point
                # image_url at Cloudflare R2.
                image_url=None,
                # example.com is IANA-reserved for documentation, so a sample event can
                # never send anyone to a real ticket page.
                ticket_url="https://example.com/tickets",
                is_active=True,
                is_sample=True,
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing sample events and tips before inserting.",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if args.reset:
            removed = db.execute(delete(Event).where(Event.is_sample.is_(True))).rowcount
            db.execute(delete(InsiderTip))
            db.commit()
            print(f"Removed {removed} sample event(s) and all tips.")

        existing = db.scalar(select(Event.id).where(Event.is_sample.is_(True)))
        if existing:
            print("Sample events already present. Re-run with --reset to replace them.")
            return

        today = now_vegas().date()
        rows = build_rows(today)
        db.add_all(rows)
        db.add_all(
            InsiderTip(venue=venue, vibe=vibe.value if vibe else None, tip=tip, priority=priority)
            for venue, vibe, tip, priority in SAMPLE_TIPS
        )
        db.commit()

        first = min(row.start_at for row in rows)
        last = max(row.start_at for row in rows)
        print(f"Inserted {len(rows)} sample events and {len(SAMPLE_TIPS)} insider tips.")
        print(f"Coverage: {first.astimezone(VEGAS_TZ):%a %d %b} to {last.astimezone(VEGAS_TZ):%a %d %b} (Vegas time)")


if __name__ == "__main__":
    main()

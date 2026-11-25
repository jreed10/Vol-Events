import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None


# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Vol Events",
    page_icon="🍊",
    layout="centered"
)

EVENTS_FILE = Path(__file__).parent / "events.json"
EVENTS_URL = "https://calendar.utk.edu/"
CAMPUS_TIMEZONE = "America/New_York"
PAGE_SIZE = 2

REQUIRED_FIELDS = {
    "title", "category", "days_from_today",
    "time", "location", "description"
}

UNCHANGED = object()   # "no category found in this message"
PAST_DATE = object()   # "user asked for a date that already passed"


def get_today():
    """Today's date on campus (not the server's timezone)."""

    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(CAMPUS_TIMEZONE)).date()
        except Exception:
            pass

    return date.today()


# ==================================================
# 2. EVENT DATABASE
# ==================================================

def start_minutes(time_text):
    """Convert the start of '7:00 PM' / '10:00 AM - 5:00 PM' to minutes."""

    match = re.match(
        r"\s*(\d{1,2}):(\d{2})\s*(AM|PM)", time_text, re.IGNORECASE
    )

    if not match:
        return 24 * 60

    hour = int(match.group(1)) % 12
    minute = int(match.group(2))

    if match.group(3).upper() == "PM":
        hour += 12

    return hour * 60 + minute


def load_events():
    """Load sample events. Returns (events, error_message)."""

    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as file:
            records = json.load(file)
    except FileNotFoundError:
        return [], f"Could not find {EVENTS_FILE.name} next to app.py."
    except json.JSONDecodeError as error:
        return [], f"{EVENTS_FILE.name} contains invalid JSON: {error}"

    if not isinstance(records, list):
        return [], f"{EVENTS_FILE.name} must contain a list of events."

    today = get_today()
    events = []

    for record in records:
        if not isinstance(record, dict) or not REQUIRED_FIELDS.issubset(record):
            continue

        try:
            offset = int(record["days_from_today"])
        except (TypeError, ValueError):
            continue

        event = record.copy()
        event["date"] = today + timedelta(days=offset)
        events.append(event)

    events.sort(
        key=lambda event: (event["date"], start_minutes(event["time"]))
    )

    return events, None


EVENTS, EVENTS_ERROR = load_events()


# ==================================================
# 3. CHATBOT CATEGORIES
# ==================================================

CATEGORIES = {
    "Upcoming Events": None,
    "UT Athletics": "Athletics",
    "Student Organizations": "Student Organizations",
    "Arts & Entertainment": "Arts & Entertainment",
    "Campus Activities": "Campus Activities",
    "Event Locations": "Event Locations"
}

CATEGORY_NAMES = {
    "Athletics": "athletics",
    "Student Organizations": "student organization",
    "Arts & Entertainment": "arts & entertainment",
    "Campus Activities": "campus activity",
    "Event Locations": "campus"
}

CATEGORY_KEYWORDS = {
    "Athletics": [
        "athletics", "athletic", "sports", "sport",
        "basketball", "football", "volleyball",
        "baseball", "game", "games", "team", "teams",
        "lady vols", "intramural", "intramurals"
    ],

    "Student Organizations": [
        "organization", "organizations", "club", "clubs",
        "student group", "student groups", "get involved",
        "student involvement", "join a club", "leadership"
    ],

    "Arts & Entertainment": [
        "arts", "art", "music", "concert", "concerts",
        "performance", "performances", "entertainment",
        "theater", "theatre", "exhibition", "exhibitions",
        "gallery"
    ],

    "Campus Activities": [
        "activities", "activity", "workshop", "workshops",
        "lecture", "lectures", "volunteer", "social",
        "community service", "wellness", "coffee", "speaker"
    ]
}

LOCATION_TERMS = [
    "location", "locations", "where", "venue", "venues"
]

GENERIC_TERMS = [
    "upcoming events", "upcoming", "all events", "events",
    "what's happening", "what is happening",
    "anything happening", "what's going on", "whats going on"
]

GENERAL_INTEREST_TERMS = [
    "something fun", "something interesting", "something to do",
    "things to do", "fun things", "anything fun",
    "with friends", "activities to do"
]

UNSUPPORTED_TOPICS = [
    "register for classes", "financial aid", "course registration",
    "class schedule", "tuition", "academic advising"
]

GREETING_RE = re.compile(
    r"^(hi|hello|hey|howdy|hiya|yo|good (morning|afternoon|evening))"
    r"( there| vols?| everyone)?$"
)
MORE_RE = re.compile(
    r"\b(more|another(?! (?:date|day|time|category|topic))|additional|"
    r"other options|other events|next one|next page|keep going)\b"
)
AFFIRM_RE = re.compile(
    r"^(yes|yeah|yep|yup|sure|ok|okay|please|absolutely|definitely|"
    r"go ahead|sounds good|show me|why not)( please| thanks)?$"
)
NEGATIVE_RE = re.compile(
    r"^(no|nope|nah|no thanks|no thank you|not really|i'm good|im good)$"
)
THANKS_RE = re.compile(r"\b(thanks|thank you|thx|appreciate it)\b")
BYE_RE = re.compile(r"\b(bye|goodbye|see you|see ya|go vols)\b")
HELP_RE = re.compile(r"\b(help|what can you do|how does this work)\b")
TICKET_RE = re.compile(
    r"(register for (an|the|this) event|sign me up|rsvp|"
    r"\b(buy|purchase|get|order)\b.*\btickets?\b)"
)
CLEAR_DATE_RE = re.compile(
    r"\b(anytime|any time|any date|any day|all dates|whenever|"
    r"clear (?:the )?(?:date|dates|filter|filters)|remove (?:the )?date)\b"
)


def has_term(text, terms):
    """Whole-word / whole-phrase matching (so 'art' won't match 'party')."""

    return any(
        re.search(rf"\b{re.escape(term)}\b", text) for term in terms
    )


# ==================================================
# 4. DATE RECOGNITION
# ==================================================

WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday"
]

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2,
    "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12
}

MONTH_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) +
    r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b"
)


def single_day(selected, today, roll_forward=False):
    """Build a (start, end, label) tuple for one day."""

    if selected < today:
        if roll_forward:
            try:
                selected = selected.replace(year=selected.year + 1)
            except ValueError:
                return PAST_DATE
        else:
            return PAST_DATE

    return selected, selected, f"{selected:%B} {selected.day}"


def get_date_range(text, today):
    """Recognize common date preferences.

    Returns (start, end, label), PAST_DATE, or None.
    """

    if re.search(r"\b(today|tonight|this evening)\b", text):
        return today, today, "today"

    if re.search(r"\btomorrow\b", text):
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow, "tomorrow"

    if re.search(r"\bnext weekend\b", text):
        monday = today + timedelta(days=7 - today.weekday())
        saturday = monday + timedelta(days=5)
        return saturday, saturday + timedelta(days=1), "next weekend"

    if re.search(r"\bweekend\b", text):
        if today.weekday() == 6:  # Sunday
            return today, today, "this weekend"

        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        return saturday, saturday + timedelta(days=1), "this weekend"

    if re.search(r"\bnext week\b", text):
        monday = today + timedelta(days=7 - today.weekday())
        return monday, monday + timedelta(days=6), "next week"

    if re.search(r"\bthis week\b", text):
        sunday = today + timedelta(days=6 - today.weekday())
        return today, sunday, "this week"

    # 2026-12-15
    match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if match:
        try:
            selected = date(
                int(match.group(1)), int(match.group(2)), int(match.group(3))
            )
        except ValueError:
            return None
        return single_day(selected, today)

    # 12/15 or 12/15/2026
    match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if match:
        try:
            month, day = int(match.group(1)), int(match.group(2))
            year_text = match.group(3)

            if year_text:
                year = int(year_text)
                if year < 100:
                    year += 2000
                return single_day(date(year, month, day), today)

            return single_day(
                date(today.year, month, day), today, roll_forward=True
            )
        except ValueError:
            return None

    # December 3 / Dec 3rd
    match = MONTH_PATTERN.search(text)
    if match:
        try:
            selected = date(
                today.year, MONTHS[match.group(1)], int(match.group(2))
            )
        except ValueError:
            return None
        return single_day(selected, today, roll_forward=True)

    # Saturday, friday, ...
    match = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", text)
    if match:
        target = WEEKDAYS.index(match.group(1))
        selected = today + timedelta(days=(target - today.weekday()) % 7)

        if selected == today:
            return today, today, "today"

        return selected, selected, selected.strftime("%A")

    return None


# ==================================================
# 5. INTENT RECOGNITION
# ==================================================

def detect_category(text, allow_generic=True):
    """Identify the category the user is interested in.

    Returns a category name, None (all events), or UNCHANGED.
    """

    for category, keywords in CATEGORY_KEYWORDS.items():
        if has_term(text, keywords):
            return category

    if has_term(text, LOCATION_TERMS):
        return "Event Locations"

    if allow_generic and has_term(text, GENERIC_TERMS):
        return None

    return UNCHANGED


# ==================================================
# 6. EVENT FILTERING
# ==================================================

def find_events(category=None, date_range=None, today=None):
    """Filter the event database based on user preferences."""

    today = today or get_today()

    results = [event for event in EVENTS if event["date"] >= today]

    if category and category != "Event Locations":
        results = [
            event for event in results
            if event["category"] == category
        ]

    if date_range:
        start, end, _ = date_range

        results = [
            event for event in results
            if start <= event["date"] <= end
        ]

    return results


# ==================================================
# 7. EVENT PRESENTATION
# ==================================================

def relative_day(event_date, today):
    days = (event_date - today).days

    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"

    return f"in {days} days"


def format_event(event, today):
    """Format event information for chatbot responses."""

    event_date = event["date"]

    return (
        f"### {event['title']}\n\n"
        f"📅 **Date:** "
        f"{event_date:%A, %B} {event_date.day}, {event_date.year} "
        f"({relative_day(event_date, today)})  \n"
        f"🕒 **Time:** {event['time']}  \n"
        f"📍 **Location:** {event['location']}\n\n"
        f"{event['description']}\n\n"
        f"_{event['category']}_"
    )


def get_introduction(category):
    """Create a category-specific introduction."""

    introductions = {
        "Athletics": (
            "Absolutely! Here are a couple of opportunities "
            "to support the Vols! 🍊"
        ),

        "Student Organizations": (
            "Great choice! Here are some opportunities to "
            "meet people and get involved around campus."
        ),

        "Arts & Entertainment": (
            "If you're looking for something creative or "
            "entertaining, here are a couple of options!"
        ),

        "Campus Activities": (
            "Here are a couple of campus activities you "
            "might enjoy!"
        )
    }

    return introductions.get(
        category,
        "Here's what I found happening around campus!"
    )


# ==================================================
# 8. RESPONSE BUILDERS
# ==================================================

def build_locations_response(date_range, today):
    """List venues and the events happening at each."""

    results = find_events(date_range=date_range, today=today)

    if not results:
        period = f" during {date_range[2]}" if date_range else ""
        return (
            f"I couldn't find any event locations{period} in my "
            "available information.\n\n"
            "Would you like to explore another date or "
            "event category?"
        )

    by_location = {}
    for event in results:
        by_location.setdefault(event["location"], []).append(event)

    lines = []
    for location in sorted(by_location):
        titles = ", ".join(
            f"{event['title']} ({event['date']:%b} {event['date'].day})"
            for event in by_location[location]
        )
        lines.append(f"📍 **{location}** — {titles}")

    header = "Here are the campus locations hosting events"
    if date_range:
        header += f" during **{date_range[2]}**"

    return (
        header + ":\n\n"
        + "\n\n".join(lines)
        + "\n\nPick an event category if you'd like to see "
        "details for a specific activity."
    )


def build_event_response(wants_more, filters_changed, today):
    """Build the event recommendation response from session state."""

    category = st.session_state.category
    date_range = st.session_state.date_range

    if category == "Event Locations":
        st.session_state.awaiting_more = False
        return build_locations_response(date_range, today)

    results = find_events(category, date_range, today)

    # ---- No matching events ----
    if not results:
        st.session_state.awaiting_more = False

        category_name = CATEGORY_NAMES.get(category, "campus")
        date_description = (
            f" during {date_range[2]}" if date_range else ""
        )

        response = (
            f"I couldn't find any upcoming {category_name} "
            f"events{date_description} in my available "
            "event information."
        )

        if date_range:
            later = find_events(category, None, today)
            if later:
                nxt = later[0]
                response += (
                    f"\n\nThe next one I have is **{nxt['title']}** on "
                    f"{nxt['date']:%A, %B} {nxt['date'].day}. "
                    "Say **\"any date\"** to see everything coming up."
                )

        return response + (
            "\n\nWould you like me to explore a different event "
            "category or look at another date?"
        )

    # ---- Paging ----
    if wants_more and not filters_changed:
        offset = st.session_state.event_offset
    else:
        offset = 0

    selected = results[offset:offset + PAGE_SIZE]

    if not selected:
        st.session_state.awaiting_more = False
        return (
            "You've now seen all the matching events in my "
            "available event information! 🍊\n\n"
            "Would you like to explore another category or "
            "change your date preferences?"
        )

    st.session_state.event_offset = offset + len(selected)

    # ---- Build response ----
    response = get_introduction(category)

    if date_range:
        response += (
            f"\n\nThese events match your search for "
            f"**{date_range[2]}**. "
            "(Say \"any date\" to clear this.)"
        )

    response += "\n\n"

    for event in selected:
        response += format_event(event, today) + "\n\n---\n\n"

    remaining = len(results) - st.session_state.event_offset

    if remaining > 0:
        st.session_state.awaiting_more = True
        response += (
            "Would you like to see more options? "
            "I can find additional events that match "
            "your interests."
        )
    else:
        st.session_state.awaiting_more = False
        response += (
            "That's everything I found matching your "
            "preferences.\n\n"
            "Would you like to explore another category "
            "or try a different date?"
        )

    return response


# ==================================================
# 9. CONVERSATION RESPONSE LOGIC
# ==================================================

def generate_response(message):
    """Generate a contextual response based on user input."""

    today = get_today()
    text = message.lower().strip().replace("’", "'")
    clean = " ".join(re.sub(r"[^\w\s']", " ", text).split())

    # ---- Greetings ----
    if GREETING_RE.match(clean):
        return (
            "Hey there! Welcome to **Vol Events! 🍊**\n\n"
            "I'm here to help you discover what's happening "
            "around the University of Tennessee.\n\n"
            "Are you interested in athletics, campus activities, "
            "student organizations or something else?"
        )

    # ---- Out-of-scope questions ----
    if any(topic in text for topic in UNSUPPORTED_TOPICS):
        return (
            "That's outside my area of expertise!\n\n"
            "I'm designed to help with UTK campus events and "
            "activities. I can help you discover sporting events, "
            "student organizations, performances and other "
            "campus activities."
        )

    # ---- Registration and tickets ----
    if TICKET_RE.search(text):
        return (
            "I can help you discover events, but I can't "
            "register you or purchase tickets.\n\n"
            "Please visit the official event page for "
            "participation and ticket information."
        )

    # ---- Event data unavailable ----
    if not EVENTS:
        return (
            "I'm having trouble loading my event information "
            "right now. Please check the official UTK calendar "
            "in the sidebar in the meantime."
        )

    # ---- "More" requests ----
    wants_more = bool(MORE_RE.search(text))

    if st.session_state.awaiting_more and AFFIRM_RE.match(clean):
        wants_more = True

    previous = (st.session_state.category, st.session_state.date_range)
    recognized = wants_more

    # ---- Category ----
    detected_category = detect_category(text, allow_generic=not wants_more)

    if detected_category is not UNCHANGED:
        st.session_state.category = detected_category
        recognized = True

    # ---- Date ----
    if CLEAR_DATE_RE.search(text):
        st.session_state.date_range = None
        recognized = True

    detected_date = get_date_range(text, today)

    if detected_date is PAST_DATE:
        return (
            "That date has already passed! I can only show "
            "upcoming events. Try a date from today onward, "
            "or ask for \"this weekend\" or \"next week\"."
        )

    if detected_date:
        st.session_state.date_range = detected_date
        recognized = True

    filters_changed = (
        st.session_state.category,
        st.session_state.date_range
    ) != previous

    # ---- General interest: ask what kind of event ----
    if (
        any(term in text for term in GENERAL_INTEREST_TERMS)
        and st.session_state.category is None
        and detected_date is None
        and not wants_more
    ):
        st.session_state.awaiting_more = False
        return (
            "I'd love to help you find something to do! 🍊\n\n"
            "What kind of experience are you looking for?\n\n"
            "- Sporting events and athletics\n"
            "- Student organizations and clubs\n"
            "- Arts, music and entertainment\n"
            "- Social activities and campus events\n\n"
            "You can also tell me when you're looking to attend!"
        )

    # ---- Nothing recognized ----
    if not recognized:
        was_waiting = st.session_state.awaiting_more
        st.session_state.awaiting_more = False

        if NEGATIVE_RE.match(clean) and was_waiting:
            return (
                "No problem! Let me know if you'd like to look at "
                "another category or a different date. 🍊"
            )

        if THANKS_RE.search(text):
            return "You're welcome! Let me know if you want to find anything else. 🍊"

        if BYE_RE.search(text):
            return "Go Vols! 🍊 Come back any time to find more events."

        if HELP_RE.search(text):
            return (
                "I can help you find UTK events! Try asking things like:\n\n"
                "- \"Any sports this weekend?\"\n"
                "- \"Show me clubs\"\n"
                "- \"Music events tomorrow\"\n"
                "- \"What's happening on Saturday?\"\n\n"
                "You can also use the buttons below."
            )

        return (
            "I'm not sure I understood that. 🍊\n\n"
            "I can help you find campus events by category "
            "(athletics, student organizations, arts, campus "
            "activities) and by date (today, this weekend, "
            "Saturday, 12/3...).\n\n"
            "Try something like **\"sports this weekend\"** or "
            "tap one of the buttons below."
        )

    return build_event_response(wants_more, filters_changed, today)


# ==================================================
# 10. CONVERSATION MANAGEMENT
# ==================================================

def handle_message(message):
    """Store a typed message and generate the chatbot response."""

    st.session_state.messages.append({
        "role": "user",
        "content": message
    })

    response = generate_response(message)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })


def handle_button(label):
    """Quick-reply buttons always start a fresh search."""

    st.session_state.messages.append({
        "role": "user",
        "content": label
    })

    st.session_state.category = CATEGORIES[label]
    st.session_state.date_range = None
    st.session_state.event_offset = 0
    st.session_state.awaiting_more = False

    response = build_event_response(
        wants_more=False,
        filters_changed=True,
        today=get_today()
    )

    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })


def reset_conversation():
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "Welcome back to Vol Events! 🍊\n\n"
            "What would you like to explore?"
        )
    }]
    st.session_state.category = None
    st.session_state.date_range = None
    st.session_state.event_offset = 0
    st.session_state.awaiting_more = False


# ==================================================
# 11. INITIALIZE SESSION STATE
# ==================================================

if "messages" not in st.session_state:

    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "Hey there! Welcome to **Vol Events! 🍊**\n\n"
            "I'm your UTK Campus Events Assistant. Whether "
            "you're looking to support the Vols, meet new "
            "people, explore campus entertainment or find "
            "something fun to do, I'm here to help!\n\n"
            "What are you interested in exploring today?"
        )
    }]

if "category" not in st.session_state:
    st.session_state.category = None

if "date_range" not in st.session_state:
    st.session_state.date_range = None

if "event_offset" not in st.session_state:
    st.session_state.event_offset = 0

if "awaiting_more" not in st.session_state:
    st.session_state.awaiting_more = False


# ==================================================
# 12. SIDEBAR
# ==================================================

with st.sidebar:

    st.title("🍊 Vol Events")

    st.write(
        "Your guide to campus activities and events "
        "at the University of Tennessee."
    )

    st.markdown("---")

    st.subheader("Official UTK Resources")

    st.link_button(
        "UTK Events Calendar",
        EVENTS_URL,
        use_container_width=True
    )

    st.markdown("---")

    st.subheader("Available Topics")

    for category_name in CATEGORIES:
        st.write(f"• {category_name}")

    st.markdown("---")

    st.subheader("Current Search")

    st.caption(
        f"Category: {st.session_state.category or 'All events'}"
    )
    st.caption(
        "Date: "
        + (
            st.session_state.date_range[2]
            if st.session_state.date_range else "Any date"
        )
    )

    st.markdown("---")

    if st.button(
        "Start New Conversation",
        use_container_width=True
    ):
        reset_conversation()
        st.rerun()


# ==================================================
# 13. MAIN CHATBOT INTERFACE
# ==================================================

st.title("🍊 Vol Events")

st.caption(
    "Your UTK Campus Events Assistant"
)

st.info(
    "Discover campus activities, explore events "
    "and find opportunities to get involved!"
)

st.warning(
    "Demo version: Recommendations use fictional "
    "sample events. Visit the official UTK calendar "
    "for verified event information."
)

if EVENTS_ERROR:
    st.error(f"Event data problem: {EVENTS_ERROR}")


# --------------------------------------------------
# DISPLAY CHAT HISTORY
# --------------------------------------------------

for chat_message in st.session_state.messages:

    with st.chat_message(chat_message["role"]):
        st.markdown(chat_message["content"])


# --------------------------------------------------
# QUICK REPLY BUTTONS
# --------------------------------------------------

st.markdown("### Explore Campus Events")

buttons = list(CATEGORIES.keys())

for row_start in range(0, len(buttons), 2):

    columns = st.columns(2)

    for index, column in enumerate(columns):

        button_index = row_start + index

        if button_index < len(buttons):

            label = buttons[button_index]

            with column:

                if st.button(
                    label,
                    key=f"category_{button_index}",
                    use_container_width=True
                ):
                    handle_button(label)
                    st.rerun()


# --------------------------------------------------
# CHAT INPUT
# --------------------------------------------------

if prompt := st.chat_input(
    "Ask Vol Events about campus activities..."
):
    handle_message(prompt)
    st.rerun()

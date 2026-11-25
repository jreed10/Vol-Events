
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st


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


# ==================================================
# 2. EVENT DATABASE
# ==================================================

def load_events():
    """Load sample events from the JSON database."""

    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as file:
            records = json.load(file)

        today = date.today()
        events = []

        for record in records:
            event = record.copy()
            event["date"] = today + timedelta(
                days=event["days_from_today"]
            )
            events.append(event)

        return sorted(events, key=lambda event: event["date"])

    except (FileNotFoundError, json.JSONDecodeError):
        return []


EVENTS = load_events()


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

CATEGORY_KEYWORDS = {
    "Athletics": [
        "athletics", "athletic", "sports", "sport",
        "basketball", "football", "volleyball",
        "baseball", "game", "games", "team", "teams",
        "vols", "lady vols"
    ],

    "Student Organizations": [
        "organization", "organizations", "club", "clubs",
        "student group", "student groups", "get involved",
        "student involvement", "join a club"
    ],

    "Arts & Entertainment": [
        "arts", "art", "music", "concert", "concerts",
        "performance", "performances", "entertainment",
        "theater", "theatre", "exhibition", "exhibitions"
    ],

    "Campus Activities": [
        "activities", "activity", "workshop", "workshops",
        "lecture", "lectures", "volunteer", "social",
        "community service", "wellness", "coffee"
    ]
}


# ==================================================
# 4. DATE RECOGNITION
# ==================================================

def get_date_range(message):
    """Recognize common date preferences."""

    text = message.lower()
    today = date.today()

    if "today" in text:
        return today, today, "today"

    if "tomorrow" in text:
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow, "tomorrow"

    if "this weekend" in text or "weekend" in text:
        days_until_saturday = (5 - today.weekday()) % 7

        if today.weekday() == 6:
            saturday = today
            sunday = today
        else:
            saturday = today + timedelta(days=days_until_saturday)
            sunday = saturday + timedelta(days=1)

        return saturday, sunday, "this weekend"

    if "next week" in text:
        days_until_monday = 7 - today.weekday()
        monday = today + timedelta(days=days_until_monday)
        sunday = monday + timedelta(days=6)

        return monday, sunday, "next week"

    # Recognize dates such as 12/15 or 2026-12-15
    patterns = [
        (r"\b\d{4}-\d{2}-\d{2}\b", "%Y-%m-%d"),
        (r"\b\d{1,2}/\d{1,2}(?:/\d{4})?\b", None)
    ]

    for pattern, date_format in patterns:
        match = re.search(pattern, text)

        if match:
            try:
                value = match.group()

                if date_format:
                    selected = datetime.strptime(
                        value, date_format
                    ).date()

                else:
                    parts = value.split("/")
                    month = int(parts[0])
                    day = int(parts[1])

                    year = (
                        int(parts[2])
                        if len(parts) == 3
                        else today.year
                    )

                    selected = date(year, month, day)

                    if len(parts) == 2 and selected < today:
                        selected = selected.replace(
                            year=today.year + 1
                        )

                if selected < today:
                    return None

                return (
                    selected,
                    selected,
                    selected.strftime("%B %d")
                )

            except ValueError:
                return None

    return None


# ==================================================
# 5. INTENT RECOGNITION
# ==================================================

def detect_category(message):
    """Identify the category the user is interested in."""

    text = message.lower()

    if any(word in text for word in [
        "location", "locations", "where", "venue", "venues"
    ]):
        return "Event Locations"

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category

    if any(phrase in text for phrase in [
        "upcoming events",
        "all events",
        "what's happening",
        "what is happening",
        "anything happening",
        "what's going on"
    ]):
        return None

    return "UNCHANGED"


# ==================================================
# 6. EVENT FILTERING
# ==================================================

def find_events(category=None, date_range=None):
    """Filter the event database based on user preferences."""

    results = EVENTS.copy()

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

def format_event(event):
    """Format event information for chatbot responses."""

    return (
        f"### {event['title']}\n\n"
        f"📅 **Date:** "
        f"{event['date'].strftime('%A, %B %d, %Y')}  \n"
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
# 8. CONVERSATION RESPONSE LOGIC
# ==================================================

def generate_response(message):
    """Generate a contextual response based on user input."""

    text = message.lower().strip()

    # ------------------------------------------------
    # GREETINGS
    # ------------------------------------------------

    if text in [
        "hi", "hello", "hey", "good morning",
        "good afternoon", "good evening"
    ]:
        return (
            "Hey there! Welcome to **Vol Events! 🍊**\n\n"
            "I'm here to help you discover what's happening "
            "around the University of Tennessee.\n\n"
            "Are you interested in athletics, campus activities, "
            "student organizations or something else?"
        )

    # ------------------------------------------------
    # OUT-OF-SCOPE QUESTIONS
    # ------------------------------------------------

    unsupported_topics = [
        "register for classes",
        "financial aid",
        "course registration",
        "class schedule",
        "tuition",
        "academic advising"
    ]

    if any(topic in text for topic in unsupported_topics):
        return (
            "That's outside my area of expertise!\n\n"
            "I'm designed to help with UTK campus events and "
            "activities. I can help you discover sporting events, "
            "student organizations, performances and other "
            "campus activities."
        )

    # ------------------------------------------------
    # EVENT REGISTRATION AND TICKETS
    # ------------------------------------------------

    if any(phrase in text for phrase in [
        "register for an event",
        "sign me up",
        "buy tickets",
        "purchase tickets"
    ]):
        return (
            "I can help you discover events, but I can't "
            "register you or purchase tickets.\n\n"
            "Please visit the official event page for "
            "participation and ticket information."
        )

    # ------------------------------------------------
    # REQUESTS FOR MORE EVENTS
    # ------------------------------------------------

    wants_more = any(phrase in text for phrase in [
        "more",
        "show me more",
        "more options",
        "other options",
        "another event",
        "additional events"
    ])

    # ------------------------------------------------
    # CATEGORY RECOGNITION
    # ------------------------------------------------

    detected_category = detect_category(message)

    if detected_category != "UNCHANGED":

        if detected_category != st.session_state.category:
            st.session_state.event_offset = 0

        st.session_state.category = detected_category

    # ------------------------------------------------
    # DATE RECOGNITION
    # ------------------------------------------------

    detected_date = get_date_range(message)

    if detected_date:

        if detected_date != st.session_state.date_range:
            st.session_state.event_offset = 0

        st.session_state.date_range = detected_date

    # ------------------------------------------------
    # HANDLE MORE REQUESTS
    # ------------------------------------------------

    if wants_more:
        st.session_state.event_offset += 2

    # ------------------------------------------------
    # RETRIEVE CONVERSATION PREFERENCES
    # ------------------------------------------------

    category = st.session_state.category
    date_range = st.session_state.date_range

    # ------------------------------------------------
    # GENERAL INTEREST / CLARIFICATION
    # ------------------------------------------------

    general_interest = any(phrase in text for phrase in [
        "something fun",
        "something interesting",
        "something to do",
        "things to do",
        "fun things",
        "anything fun",
        "with friends",
        "activities to do"
    ])

    if (
        general_interest
        and category is None
        and not wants_more
    ):
        return (
            "I'd love to help you find something to do! 🍊\n\n"
            "What kind of experience are you looking for?\n\n"
            "- Sporting events and athletics\n"
            "- Student organizations and clubs\n"
            "- Arts, music and entertainment\n"
            "- Social activities and campus events\n\n"
            "You can also tell me when you're looking to attend!"
        )

    # ------------------------------------------------
    # EVENT LOCATIONS
    # ------------------------------------------------

    if category == "Event Locations":

        results = find_events(date_range=date_range)

        if not results:
            return (
                "I couldn't find any event locations in my "
                "available information for that time period.\n\n"
                "Would you like to explore another date or "
                "event category?"
            )

        locations = sorted(set(
            event["location"] for event in results
        ))

        return (
            "Here are some campus locations associated with "
            "events in my available information:\n\n"
            + "\n".join(
                f"📍 **{location}**"
                for location in locations[:6]
            )
            + "\n\nSelect an event category if you'd like "
            "to see specific activities happening at these venues."
        )

    # ------------------------------------------------
    # FIND MATCHING EVENTS
    # ------------------------------------------------

    results = find_events(category, date_range)

    # ------------------------------------------------
    # NO MATCHING EVENTS
    # ------------------------------------------------

    if not results:

        category_name = (
            category.lower() if category else "campus"
        )

        date_description = (
            f" during {date_range[2]}"
            if date_range else ""
        )

        return (
            f"I couldn't find any upcoming {category_name} "
            f"events{date_description} in my available "
            "event information.\n\n"
            "Would you like me to explore a different event "
            "category or look at another date?"
        )

    # ------------------------------------------------
    # SELECT RECOMMENDATIONS
    # ------------------------------------------------

    offset = st.session_state.event_offset

    selected = results[offset:offset + 2]

    if not selected:

        return (
            "You've now seen all the matching events in my "
            "available event information! 🍊\n\n"
            "Would you like to explore another category or "
            "change your date preferences?"
        )

    # ------------------------------------------------
    # BUILD RESPONSE
    # ------------------------------------------------

    response = get_introduction(category)

    if date_range:
        response += (
            f"\n\nThese events match your search for "
            f"**{date_range[2]}**."
        )

    response += "\n\n"

    for event in selected:
        response += format_event(event) + "\n\n---\n\n"

    # ------------------------------------------------
    # FOLLOW-UP SUGGESTIONS
    # ------------------------------------------------

    remaining = len(results) - (
        offset + len(selected)
    )

    if remaining > 0:

        response += (
            "Would you like to see more options? "
            "I can find additional events that match "
            "your interests."
        )

    else:

        response += (
            "That's everything I found matching your "
            "preferences.\n\n"
            "Would you like to explore another category "
            "or try a different date?"
        )

    return response


# ==================================================
# 9. CONVERSATION MANAGEMENT
# ==================================================

def handle_message(message):
    """Store messages and generate chatbot responses."""

    st.session_state.messages.append({
        "role": "user",
        "content": message
    })

    response = generate_response(message)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })


# ==================================================
# 10. INITIALIZE SESSION STATE
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


# ==================================================
# 11. SIDEBAR
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

    if st.button(
        "Start New Conversation",
        use_container_width=True
    ):

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

        st.rerun()


# ==================================================
# 12. MAIN CHATBOT INTERFACE
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


# --------------------------------------------------
# DISPLAY CHAT HISTORY
# --------------------------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


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

                    handle_message(label)
                    st.rerun()


# --------------------------------------------------
# CHAT INPUT
# --------------------------------------------------

if prompt := st.chat_input(
    "Ask Vol Events about campus activities..."
):

    handle_message(prompt)
    st.rerun()


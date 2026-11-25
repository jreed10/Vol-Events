
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Vol Events",
    page_icon="🍊",
    layout="centered"
)

EVENTS_FILE = Path(__file__).parent / "events.json"
EVENTS_URL = "https://calendar.utk.edu/"


# --------------------------------------------------
# EVENT DATA
# --------------------------------------------------

def load_events():
    """Load demonstration events from the JSON file."""

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

        return sorted(events, key=lambda x: x["date"])

    except (FileNotFoundError, json.JSONDecodeError):
        return []


EVENTS = load_events()


# --------------------------------------------------
# CHATBOT CATEGORIES
# --------------------------------------------------

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
        "athletics", "sports", "basketball", "football",
        "volleyball", "baseball", "game", "games", "sport"
    ],
    "Student Organizations": [
        "organization", "organizations", "club", "clubs",
        "student group", "student groups"
    ],
    "Arts & Entertainment": [
        "arts", "art", "music", "concert", "concerts",
        "performance", "performances", "entertainment",
        "theater", "theatre"
    ],
    "Campus Activities": [
        "activities", "activity", "workshop", "workshops",
        "lecture", "lectures", "volunteer", "social",
        "community service"
    ]
}


# --------------------------------------------------
# DATE RECOGNITION
# --------------------------------------------------

def get_date_range(message):
    """Recognize basic date preferences."""

    text = message.lower()
    today = date.today()

    if "today" in text:
        return today, today, "today"

    if "tomorrow" in text:
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow, "tomorrow"

    if "this weekend" in text or "weekend" in text:
        days_until_saturday = (5 - today.weekday()) % 7
        saturday = today + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)

        return saturday, sunday, "this weekend"

    if "next week" in text:
        days_until_monday = 7 - today.weekday()
        monday = today + timedelta(days=days_until_monday)
        sunday = monday + timedelta(days=6)

        return monday, sunday, "next week"

    # Recognize dates such as 12/15 or 2026-12-15
    for pattern, date_format in [
        (r"\b\d{4}-\d{2}-\d{2}\b", "%Y-%m-%d"),
        (r"\b\d{1,2}/\d{1,2}(?:/\d{4})?\b", None)
    ]:
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
                    year = int(parts[2]) if len(parts) == 3 else today.year

                    selected = date(year, month, day)

                    if len(parts) == 2 and selected < today:
                        selected = selected.replace(year=today.year + 1)

                return selected, selected, selected.strftime("%B %d")

            except ValueError:
                return None

    return None


# --------------------------------------------------
# INTENT RECOGNITION
# --------------------------------------------------

def detect_category(message):
    """Identify the category the user is asking about."""

    text = message.lower()

    if "location" in text or "where" in text or "venue" in text:
        return "Event Locations"

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(word in text for word in keywords):
            return category

    if any(word in text for word in [
        "upcoming events", "all events", "what's happening",
        "what is happening", "anything happening"
    ]):
        return None

    return "UNCHANGED"


# --------------------------------------------------
# EVENT FILTERING
# --------------------------------------------------

def find_events(category=None, date_range=None):
    """Filter events using the current conversation preferences."""

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


def format_event(event):
    """Format an event for display in the conversation."""

    return (
        f"**{event['title']}**\n\n"
        f"📅 {event['date'].strftime('%A, %B %d, %Y')}\n\n"
        f"🕒 {event['time']}\n\n"
        f"📍 {event['location']}\n\n"
        f"{event['description']}\n\n"
        f"_{event['category']}_"
    )


# --------------------------------------------------
# CHATBOT RESPONSE LOGIC
# --------------------------------------------------

def generate_response(message):
    """Generate a response based on the user's message."""

    text = message.lower().strip()

    if any(word in text for word in [
        "register", "registration", "buy tickets",
        "purchase tickets", "sign me up"
    ]):
        return (
            "I can help you discover events, but I can't "
            "register you or purchase tickets. Please visit "
            "the official event page for participation details."
        )

    # Handle greetings
    if text in ["hi", "hello", "hey", "good morning", "good afternoon"]:
        return (
            "Hey there! Welcome to Vol Events! 🍊 "
            "What kind of campus events are you interested in?"
        )

    # Identify unsupported questions
    more_request = any(phrase in text for phrase in [
        "more", "more options", "show more",
        "other options", "another event"
    ])

    recognized_category = detect_category(message)
    recognized_date = get_date_range(message)

    general_event_question = (
        "event" in text or
        "happening" in text or
        "going on" in text
    )

    if (
        recognized_category == "UNCHANGED"
        and not recognized_date
        and not more_request
        and not general_event_question
    ):
        return (
            "I'm sorry, but I can only help with UTK campus "
            "events and activities. I can help you explore "
            "athletics, student organizations, arts and "
            "entertainment, campus activities or event locations. "
            "What would you like to explore?"
        )

    # Handle requests for more recommendations
    if any(phrase in text for phrase in [
        "more", "more options", "show more",
        "other options", "another event"
    ]):
        st.session_state.event_offset += 2

    else:
        # Update category only when a new category is identified
        detected = detect_category(message)

        if detected != "UNCHANGED":
            if detected != st.session_state.category:
                st.session_state.event_offset = 0

            st.session_state.category = detected

        # Update date preference when one is mentioned
        detected_date = get_date_range(message)

        if detected_date:
            st.session_state.date_range = detected_date
            st.session_state.event_offset = 0

    category = st.session_state.category
    date_range = st.session_state.date_range

    # Event location requests
    if category == "Event Locations":
        results = find_events(date_range=date_range)

        if not results:
            return (
                "I couldn't find events with available location "
                "information for that time period. Would you like "
                "to explore another date or event category?"
            )

        locations = sorted(set(
            event["location"] for event in results
        ))

        return (
            "Here are some campus venues appearing in my "
            "available event information:\n\n"
            + "\n".join(f"📍 {location}" for location in locations[:6])
            + "\n\nYou can select an event category to find "
            "specific activities and their locations."
        )

    # Find matching events
    results = find_events(category, date_range)

    if not results:
        category_name = category or "events"

        date_description = (
            f" for {date_range[2]}"
            if date_range else ""
        )

        return (
            f"I couldn't find any upcoming {category_name.lower()}"
            f"{date_description} in my available event information.\n\n"
            "Would you like me to explore a different event "
            "category or another date?"
        )

    # Display one or two recommendations
    offset = st.session_state.event_offset
    selected = results[offset:offset + 2]

    if not selected:
        return (
            "I've shown you all the matching events in my "
            "available event information. Would you like to "
            "explore a different category or date?"
        )

    heading = "Here are a couple of events you might enjoy!"

    if len(selected) == 1:
        heading = "Here's an event you might enjoy!"

    response = heading + "\n\n"

    for event in selected:
        response += format_event(event) + "\n\n---\n\n"

    remaining = len(results) - (offset + len(selected))

    if remaining > 0:
        response += (
            "Would you like to see more options? "
            "Just ask me to show you more!"
        )
    else:
        response += (
            "That's everything I found matching your "
            "preferences. You can explore another category "
            "or change your date preferences."
        )

    return response


# --------------------------------------------------
# CONVERSATION MANAGEMENT
# --------------------------------------------------

def handle_message(message):
    """Add a user message and generate a chatbot response."""

    st.session_state.messages.append({
        "role": "user",
        "content": message
    })

    response = generate_response(message)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })


if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "Hey there! Welcome to **Vol Events! 🍊**\n\n"
            "I'm your UTK Campus Events Assistant. I can help "
            "you discover sporting events, student organizations, "
            "performances and other activities around campus.\n\n"
            "What would you like to explore?"
        )
    }]

if "category" not in st.session_state:
    st.session_state.category = None

if "date_range" not in st.session_state:
    st.session_state.date_range = None

if "event_offset" not in st.session_state:
    st.session_state.event_offset = 0


# --------------------------------------------------
# USER INTERFACE
# --------------------------------------------------

st.title("🍊 Vol Events")
st.caption("Your UTK Campus Events Assistant")

st.info(
    "Explore campus activities, discover events and "
    "find opportunities to get involved!"
)

# Display demonstration data notice
st.warning(
    "Demo version: Event recommendations use fictional "
    "sample records. Check the official UTK calendar for "
    "verified event information."
)

# Sidebar resources
with st.sidebar:
    st.header("About Vol Events")

    st.write(
        "Vol Events helps the University of Tennessee "
        "community discover campus events and activities."
    )

    st.markdown("### Official UTK Resources")

    st.link_button(
        "UTK Events Calendar",
        EVENTS_URL,
        use_container_width=True
    )

    st.markdown("---")

    st.write("**Available Topics**")

    for category in CATEGORIES:
        st.write(f"• {category}")

    if st.button("Start New Conversation"):
        st.session_state.messages = [{
            "role": "assistant",
            "content": (
                "Welcome back to Vol Events! 🍊 "
                "What would you like to explore?"
            )
        }]

        st.session_state.category = None
        st.session_state.date_range = None
        st.session_state.event_offset = 0

        st.rerun()


# Display conversation history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Quick reply buttons
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


# User text input
if prompt := st.chat_input(
    "Ask Vol Events about campus activities..."
):
    handle_message(prompt)
    st.rerun()


"""User-facing strings. One place to edit copy."""

TOPIC_NEWEST = "Newest"
TOPIC_POPULAR = "Popular"
TOPIC_FORYOU = "For You"

WELCOME_NEWEST = (
    "<b>Newest</b>\n\n"
    "Real-time posts from channels you add. "
    "Forward me any post from a channel to add it to your feed."
)

WELCOME_POPULAR = (
    "<b>Popular</b>\n\n"
    "Top posts from your channels, ranked by reactions, refreshed every few hours."
)

WELCOME_FORYOU = (
    "<b>For You</b>\n\n"
    "Channels you might enjoy, based on what people with similar taste read. "
    "Tap a card to add a channel to your feed."
)

START_NEW_USER = (
    "Hi! I'll create a personal feed for you in three topics: "
    "<b>Newest</b>, <b>Popular</b>, and <b>For You</b>.\n\n"
    "You need a Telegram group with <b>Topics</b> enabled. Already have one? Skip to step 2.\n\n"
    "<b>1. Create the group</b>\n"
    "Tap the pencil icon → <b>New Group</b> → name it anything (e.g. 'My Feed').\n\n"
    "<b>2. Enable Topics</b>\n"
    "Tap <b>Edit</b> at the top of the group → scroll down → toggle <b>Topics</b> ON → Save.\n\n"
    "<b>3. Add me as admin</b>\n"
    "Still in the group info → <b>Administrators</b> → <b>Add Administrator</b> → "
    "find me → enable <b>Manage Topics</b> → Done.\n\n"
    "That's it. I'll set up your feed the moment you add me."
)

START_ACTIVE_USER = (
    "Your feed is active.\n\n"
    "Forward me any post from a participating channel to add it to your feed.\n\n"
    "Commands:\n"
    "/list - what's in your feed\n"
    "/pause - stop new posts globally\n"
    "/resume - resume\n"
    "/privacy - what data I store\n"
)

START_PAUSED_USER = (
    "Your feed is paused. Send /resume to start receiving posts again."
)

SETUP_DONE = (
    "Your feed is ready. Three topics have been created in your supergroup: "
    "<b>Newest</b>, <b>Popular</b>, and <b>For You</b>.\n\n"
    "Now forward me any post from a channel you follow to add it to your feed."
)

ADD_OK = "Added <b>{title}</b> to your feed. New posts will appear in Newest."
ADD_ALREADY_SUBSCRIBED = "<b>{title}</b> is already in your feed."
ADD_NOT_PARTICIPATING = (
    "<b>{title}</b> hasn't joined the network yet. The channel admin needs to add me "
    "as an administrator there first."
)
ADD_NOT_MEMBER = (
    "You need to join <b>{title}</b> in Telegram first, then forward me a post from it."
)
ADD_UNKNOWN_CHANNEL = (
    "I couldn't read which channel this was forwarded from. The original poster may have "
    "hidden their identity. Try a different post from the same channel."
)

NO_FORWARD = (
    "Forward me a post from a channel to add it to your feed. "
    "Use the share icon in Telegram -> select me."
)

NEED_SUPERGROUP = (
    "You haven't set up your feed supergroup yet. Send /start for instructions."
)

PAUSED_OK = "Paused. New posts won't arrive until you /resume."
RESUMED_OK = "Resumed."

LIST_EMPTY = "Your feed is empty. Forward me a post from a channel to add it."
LIST_HEADER = "<b>Your feed</b> ({count} channel{plural}):"

POPULAR_HEADER = "From <b>{title}</b> - {reactions} reactions"
FORYOU_CARD = (
    "<b>{title}</b>\n"
    "{description}\n\n"
    "{subscriber_count} other readers follow this channel."
)

PRIVACY_SUMMARY = (
    "<b>Your privacy</b>\n\n"
    "I only store what I need to run your feed: your Telegram ID, your feed group and "
    "topic IDs, which channels you added, and lightweight references to recent posts "
    "(channel + message ID, a short preview, reaction counts) used to rank Popular.\n\n"
    "- I deliver a channel's posts to you only if you're a verified member of it.\n"
    "- I forward posts within Telegram - I don't archive message contents or media.\n"
    "- I never sell your data or use it to train AI/ML models.\n"
    "- Post references are auto-deleted after a few days.\n\n"
    "Manage your data: /list to remove channels, /pause to stop delivery. To erase "
    "everything, remove me from your feed group or just ask."
)

PRIVACY_WITH_URL = (
    "<b>Your privacy</b>\n\n"
    "I only store what I need to run your feed and never use your data to train AI or "
    "sell it. Full policy: {url}\n\n"
    "Manage your data with /list and /pause at any time."
)

OWNER_THANKS = (
    "Thanks for adding me as administrator to <b>{title}</b>.\n\n"
    "Your channel is now in the network. Members of your channel can now receive "
    "its posts in their personal feed automatically.\n\n"
    "I'll never post in or modify your channel. Remove me as administrator any time to opt out."
)

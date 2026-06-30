import os

# আপনার Telegram user ID — bot শুধু এই ID গুলো থেকে command accept করবে
# আপনার ID জানতে @userinfobot এ /start দিন
ALLOWED_USER_IDS = [
    int(x.strip())
    for x in os.environ.get("ALLOWED_USER_IDS", "").split(",")
    if x.strip()
]

# Client list — নতুন client যোগ করতে এখানে add করুন
CLIENTS = {
    "SKF Boosting": {
        "account_id": "act_1555254628481247",
        "active": True,
    },
    "SK Sazzad": {
        "account_id": "act_835548522569347",
        "active": True,
    },
    "Masud - Baby Nest": {
        "account_id": "act_2297576714060575",
        "active": True,
    },
    "Pejus - Shoe Hub": {
        "account_id": "act_1865816114068999",
        "active": True,
    },
}

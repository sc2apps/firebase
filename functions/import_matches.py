import asyncio
from datetime import datetime, timedelta

from db import process_matches
from firebase_admin import credentials, firestore, initialize_app

import sc2reader

cred = credentials.Certificate("service-account.json")
app = initialize_app(
    cred
)
db = firestore.client()

checkUntil = datetime(2023, 1, 1, 1, 0, 0)
# checkUntil = datetime(2023, 10, 20, 0, 0, 0)
asyncio.run(process_matches(checkUntil))
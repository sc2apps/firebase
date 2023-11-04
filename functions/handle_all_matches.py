from datetime import datetime, timedelta

from firebase_admin import credentials, firestore, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentSnapshot
from utils import MATCHES_COLLECTION, handle_match

import sc2reader

cred = credentials.Certificate("service-account.json")
app = initialize_app(cred)
db = firestore.client()


def paginate_and_handle_matches(handle_after=None):
    db = firestore.client()
    # Change this to the number of documents you want to process in a single batch
    page_size = 100

    # Initial query to get the first page
    query = db.collection(MATCHES_COLLECTION)
    if handle_after:
        query = query.where(filter=FieldFilter('createdAt', '>', handle_after)
                            )
    query = query.where(filter=FieldFilter('regionId', '==', 2))
    query = query.order_by(
        'createdAt', direction=firestore.Query.ASCENDING
    ).limit(page_size)

    last_doc = None
    more_pages = True

    while more_pages:
        matches: list[DocumentSnapshot] = query.stream()
        match_count = 0

        for match in matches:
            match_count += 1
            match_data = match.to_dict()
            print(f"Parsing match {match.id}")
            if not match_data['match']['completedAt']:
                print("Deleting old incomplete match")
                match.reference.delete()
                continue
            if 'wonElo' in match_data:
                print(f"Already handled match {match.id}")
            else:
                handle_match(db, match.reference, match.to_dict())
            last_doc = match

        # If the number of matches in this page is less than our page size, then no more pages left
        if match_count < page_size:
            more_pages = False
        else:
            # Set the start point for the next page after the last document from this page
            query = db.collection(MATCHES_COLLECTION).order_by(
                'createdAt', direction=firestore.Query.ASCENDING).start_after(last_doc).limit(page_size)


paginate_and_handle_matches()

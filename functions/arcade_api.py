
import asyncio
from datetime import datetime, timedelta

import httpx
from utils import (MOD_IDS, REQUEST_LIMIT, REQUEST_WINDOW, mod_document,
                   mod_name)

request_count = 0
window_start_time = datetime.utcnow()


async def fetch_lobbies_for_region_mod(region, mod_id, checkUntil):
    global request_count, window_start_time
    lobbies = []
    after = ''

    async with httpx.AsyncClient() as client:
        while True:
            # If we've made 100 requests, wait for the remainder of the 40 seconds
            if request_count >= REQUEST_LIMIT:
                elapsed_time = (datetime.utcnow() -
                                window_start_time).seconds
                if elapsed_time < REQUEST_WINDOW:
                    await asyncio.sleep(REQUEST_WINDOW - elapsed_time)
                request_count = 0
                window_start_time = datetime.utcnow()

            url = f"https://sc2arcade.com/api/lobbies/history?regionId={region}&mapId={mod_id}&includeMatchResult=true&includeMatchPlayers=true&includeMapInfo=true&includeSlots=true&includeSlotsProfile=true&after={after}&limit=100"
            print(f"Pulling Url: {url}")

            start_time = datetime.now()
            try:
                response = await client.get(url, timeout=5)
            except Exception as exc:
                delta = datetime.now() - start_time
                print(
                    f"Failed to load url after {delta.seconds} seconds:\n{url}\n{exc}")
                return lobbies
            request_count += 1

            responseJson = response.json()
            try:
                after = responseJson['page']['next']
                results = responseJson['results']
                lastResult = results[len(results) - 1]

                lastCreated = lastResult['createdAt']
                lastCreated = datetime.fromisoformat(lastCreated[0:-1])

                for data in responseJson['results']:
                    if data['status'] == 'started':
                        lobbies.append(data)

                print(f'Last created: {lastCreated}')
                if lastCreated < checkUntil:
                    break
            except Exception as error:
                print(f"Failed to parse {url}")
                print(error)
            if not after:
                break

    return lobbies

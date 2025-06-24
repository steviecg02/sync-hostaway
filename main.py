import os
import time
import logging
import requests
import psycopg2
import psycopg2.extras
import concurrent.futures
import json
from urllib.parse import urljoin
from uuid import UUID
from datetime import datetime, date
from dateutil import parser as date_parser
from typing import List, Dict, Any, Tuple

# === ENV VARIABLES ===
HOSTAWAY_CLIENT_ID = os.getenv("HOSTAWAY_CLIENT_ID")
HOSTAWAY_CLIENT_SECRET = os.getenv("HOSTAWAY_CLIENT_SECRET")
HOSTAWAY_ACCESS_TOKEN = os.getenv("HOSTAWAY_ACCESS_TOKEN")  # Optional access token
POSTGRES_URL = os.getenv("POSTGRES_URL")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SAVE_JSON = os.getenv("SAVE_JSON", "false").lower() == "true"

# === LOGGING SETUP ===
logging.basicConfig(level=LOG_LEVEL,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# === CONSTANTS ===
HOSTAWAY_BASE_URL = "https://api.hostaway.com/v1/"
TOKEN_URL = "https://api.hostaway.com/v1/accessTokens"
HEADERS = {"Content-Type": "application/json"}

# === AUTH ===
def get_access_token():
    if HOSTAWAY_ACCESS_TOKEN:
        logger.info("Using supplied access token from environment.")
        return HOSTAWAY_ACCESS_TOKEN

    logger.info("Requesting new access token...")
    res = requests.post(TOKEN_URL, json={
        "grant_type": "client_credentials",
        "client_id": HOSTAWAY_CLIENT_ID,
        "client_secret": HOSTAWAY_CLIENT_SECRET
    })
    res.raise_for_status()
    token = res.json().get("access_token")
    return token

# === PMS ID FETCH ===
def get_pms_id():
    with psycopg2.connect(POSTGRES_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT pms_id FROM pms WHERE type = 'hostaway' AND account_id = %s",
                (HOSTAWAY_CLIENT_ID,)
            )
            row = cur.fetchone()
            if not row:
                raise Exception("PMS record not found. Check HOSTAWAY_CLIENT_ID is set correctly.")
            return row["pms_id"]

# === PAGINATION HANDLER ===
def paginate(endpoint, token):
    page = 0
    limit = 100
    all_results = []
    while True:
        offset = page * limit
        res = requests.get(urljoin(HOSTAWAY_BASE_URL, endpoint),
                           headers={"Authorization": f"Bearer {token}"},
                           params={"limit": limit, "offset": offset})
        if res.status_code == 429:
            logger.warning("Rate limited. Retrying...")
            time.sleep(min(60, 2 ** page))
            continue
        res.raise_for_status()
        data = res.json()
        page_results = data.get("result", [])
        all_results.extend(page_results)
        logger.info(f"Fetched {len(page_results)} records from {endpoint} (offset {offset})")
        if len(page_results) < limit:
            break
        page += 1
    return all_results

# === SAVE RAW JSON ===
def optionally_save_json(endpoint, data):
    if SAVE_JSON:
        with open(f"{endpoint.replace('/', '_')}.json", "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {endpoint} output to {endpoint.replace('/', '_')}.json")

# === DATABASE ===
def insert_records(table, records, conflict_keys):
    if not records:
        logger.info(f"No new records to insert into {table}")
        return
    with psycopg2.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cols = records[0].keys()
            sql = f"""
            INSERT INTO {table} ({', '.join(cols)})
            VALUES %s
            ON CONFLICT ({', '.join(conflict_keys)}) DO NOTHING
            """
            values = [
                [json.dumps(r[col]) if isinstance(r[col], dict) else r[col] for col in cols]
                for r in records
            ]
            psycopg2.extras.execute_values(
                cur, sql, values, template=None, page_size=100
            )
        conn.commit()
        logger.info(f"Inserted {len(records)} records into {table}")

# === DATA FETCHERS ===
def fetch_data(endpoint, token):
    logger.info(f"Fetching data from {endpoint}...")
    data = paginate(endpoint, token)
    optionally_save_json(endpoint, data)
    return data

def fetch_conversation_messages(conversations, token):
    logger.info("Fetching conversation messages by ID...")
    all_messages = []

    def fetch_messages_for_convo(convo):
        convo_id = convo["id"]
        url = urljoin(HOSTAWAY_BASE_URL, f"conversations/{convo_id}/messages")
        page = 1
        messages = []
        while True:
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params={"page": page})
            if res.status_code == 429:
                logger.warning(f"Rate limited on messages for convo {convo_id}. Retrying...")
                time.sleep(min(60, 2 ** page))
                continue
            res.raise_for_status()
            data = res.json()
            page_messages = data.get("result", [])
            messages.extend(page_messages)
            total_pages = data.get("totalPages", 1)
            logger.info(f"Fetched page {page}/{total_pages} for conversation {convo_id} with {len(page_messages)} messages")
            if page >= total_pages:
                break
            page += 1
        return messages

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_messages_for_convo, c) for c in conversations]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            all_messages.extend(result)

    optionally_save_json("conversation_messages", all_messages)
    return all_messages

def normalize_listings(raw_listings: List[Dict], pms_id) -> List[Dict]:
    normalized = []
    for listing in raw_listings:
        normalized.append({
            "hostaway_id": str(listing["id"]),
            "pms_id": pms_id,
            "source_type": "api_pull",
            "pms_type": "hostaway",
            "pms_meta": listing,
            "full_address": listing["address"],
            "latitude": listing["lat"],
            "longitude": listing["lng"],
            "unit_type": listing["roomType"],
            "bedrooms": listing["bedroomsNumber"],
            "beds": listing["bedsNumber"],
            "bathrooms": listing["bathroomsNumber"],
            "max_guests": listing["personCapacity"],
            "check_in_time": listing["checkInTimeStart"],
            "check_out_time": listing["checkOutTime"],
            "cleaning_fee": listing["cleaningFee"],
            "currency": listing["currencyCode"],
            "timezone": listing["timeZoneName"]
        })
    logger.info(f"Prepared {len(normalized)} listings for insert")
    return normalized

def insert_listings(conn, listings: List[Dict]) -> Dict[str, UUID]:
    """
    Inserts or updates listings using full_address as the conflict key.
    Returns a mapping from Hostaway listing ID (from pms_meta['id']) to internal listing_id.
    """
    if not listings:
        return {}

    columns = [
        "pms_id", "source_type", "pms_type", "pms_meta", "full_address", "latitude",
        "longitude", "unit_type", "bedrooms", "beds", "bathrooms", "max_guests",
        "check_in_time", "check_out_time", "cleaning_fee", "currency", "timezone"
    ]

    sql = f"""
    INSERT INTO listings ({', '.join(columns)})
    VALUES %s
    ON CONFLICT (full_address) DO UPDATE SET
        pms_meta = EXCLUDED.pms_meta,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        unit_type = EXCLUDED.unit_type,
        bedrooms = EXCLUDED.bedrooms,
        beds = EXCLUDED.beds,
        bathrooms = EXCLUDED.bathrooms,
        max_guests = EXCLUDED.max_guests,
        check_in_time = EXCLUDED.check_in_time,
        check_out_time = EXCLUDED.check_out_time,
        cleaning_fee = EXCLUDED.cleaning_fee,
        currency = EXCLUDED.currency,
        timezone = EXCLUDED.timezone,
        pms_id = EXCLUDED.pms_id,
        pms_type = EXCLUDED.pms_type
    WHERE 
        listings.latitude IS DISTINCT FROM EXCLUDED.latitude OR
        listings.longitude IS DISTINCT FROM EXCLUDED.longitude OR
        listings.unit_type IS DISTINCT FROM EXCLUDED.unit_type OR
        listings.bedrooms IS DISTINCT FROM EXCLUDED.bedrooms OR
        listings.beds IS DISTINCT FROM EXCLUDED.beds OR
        listings.bathrooms IS DISTINCT FROM EXCLUDED.bathrooms OR
        listings.max_guests IS DISTINCT FROM EXCLUDED.max_guests OR
        listings.check_in_time IS DISTINCT FROM EXCLUDED.check_in_time OR
        listings.check_out_time IS DISTINCT FROM EXCLUDED.check_out_time OR
        listings.cleaning_fee IS DISTINCT FROM EXCLUDED.cleaning_fee OR
        listings.currency IS DISTINCT FROM EXCLUDED.currency OR
        listings.timezone IS DISTINCT FROM EXCLUDED.timezone OR
        listings.pms_id IS DISTINCT FROM EXCLUDED.pms_id OR
        listings.pms_type IS DISTINCT FROM EXCLUDED.pms_type OR
        listings.pms_meta IS DISTINCT FROM EXCLUDED.pms_meta
    """

    values = [
        [json.dumps(listing[col], sort_keys=True) if isinstance(listing[col], dict) else listing[col] for col in columns]
        for listing in listings
    ]

    hostaway_ids = [listing["pms_meta"]["id"] for listing in listings]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, page_size=100)

        cur.execute(
            "SELECT listing_id, pms_meta->>'id' AS hostaway_id FROM listings WHERE CAST(pms_meta->>'id' AS INTEGER) = ANY(%s)",
            (hostaway_ids,)
        )

        rows = cur.fetchall()
        return {row[1]: row[0] for row in rows}  # {hostaway_id: listing_id}

def normalize_guests(raw_reservations: List[Dict], pms_id: UUID) -> List[Dict]:
    """
    Normalize guest data from reservation records.
    Only keeps one guest per reservation if reservation status is accepted.
    """
    valid_statuses = {"new", "modified", "cancelled"}
    guests = []

    for res in raw_reservations:
        if res.get("status") not in valid_statuses:
            continue

        full_name = res.get("guestName")
        email = res.get("guestEmail")
        phone = res.get("phone")

        # skip if all identity fields are blank
        if not (full_name or email or phone):
            continue

        guests.append({
            "pms_id": pms_id,
            "source_type": "api_pull",
            "full_name": full_name,
            "first_name": res.get("guestFirstName"),
            "last_name": res.get("guestLastName"),
            "email": email,
            "phone": phone,
        })

    logger.info(f"Prepared {len(guests)} guests for insert")
    return guests

def insert_guests(conn, guests: List[Dict]) -> Dict[str, UUID]:
    if not guests:
        logger.info("No guests to insert.")
        return {}

    guest_id_map = {}
    seen_identities = set()
    deduped = []

    for g in guests:
        identity = f"{g['pms_id']}_{g.get('email') or g.get('phone') or g.get('full_name') or ''}"
        if identity in seen_identities:
            logger.warning(f"Duplicate guest_identity in batch: {identity}")
            continue
        seen_identities.add(identity)
        deduped.append(g)

    if not deduped:
        logger.info("No unique guests to insert.")
        return {}

    columns = [k for k in deduped[0].keys() if k != "guest_identity"]

    sql = f"""
    INSERT INTO guests ({', '.join(columns)})
    VALUES %s
    ON CONFLICT (guest_identity) DO UPDATE
    SET
        full_name = EXCLUDED.full_name,
        first_name = EXCLUDED.first_name,
        last_name = EXCLUDED.last_name,
        email = EXCLUDED.email,
        phone = EXCLUDED.phone,
        source_type = EXCLUDED.source_type,
        pms_id = EXCLUDED.pms_id
    WHERE (
        guests.full_name IS DISTINCT FROM EXCLUDED.full_name OR
        guests.first_name IS DISTINCT FROM EXCLUDED.first_name OR
        guests.last_name IS DISTINCT FROM EXCLUDED.last_name OR
        guests.email IS DISTINCT FROM EXCLUDED.email OR
        guests.phone IS DISTINCT FROM EXCLUDED.phone OR
        guests.pms_id IS DISTINCT FROM EXCLUDED.pms_id
    )
    """

    with conn.cursor() as cur:
        values = [
            [json.dumps(g[col]) if isinstance(g[col], dict) else g[col] for col in columns]
            for g in deduped
        ]
        psycopg2.extras.execute_values(cur, sql, values, page_size=100)

        # ✅ SELECT all guests under this pms_id
        pms_id = deduped[0]['pms_id']
        cur.execute(
            """
            SELECT guest_id, guest_identity
            FROM guests
            WHERE pms_id = %s
            """,
            (pms_id,)
        )
        for guest_id, identity in cur.fetchall():
            guest_id_map[identity] = guest_id

    conn.commit()
    return guest_id_map

def normalize_channel_type(channel_id):
    map = {
        2018: 'airbnb',
        2005: 'booking_com',
        2000: 'direct',
        2013: 'direct',
        2015: 'direct',
        2017: 'direct',
        2002: 'vrbo',
        2009: 'vrbo',
        2010: 'vrbo',
    }
    return map.get(channel_id, 'direct')

def normalize_reservations(raw_reservations: List[Dict], pms_id: UUID,
                            listing_id_map: Dict[str, UUID],
                            guest_id_map: Dict[str, UUID]) -> List[Dict]:
    reservations = []
    real_statuses = {"new", "modified", "cancelled"}

    for res in raw_reservations:
        hostaway_id = str(res.get("listingMapId"))
        listing_id = listing_id_map.get(hostaway_id)

        identity_key = f"{pms_id}_{res.get('guestEmail') or res.get('phone') or res.get('guestName')}"
        guest_id = guest_id_map.get(identity_key)

        reservations.append({
            "listing_id": listing_id,
            "reservation_date": res["reservationDate"],
            "check_in_date": res["arrivalDate"],
            "check_out_date": res["departureDate"],
            "check_in_time": res.get("checkInTime", 15),
            "check_out_time": res.get("checkOutTime", 11),
            "nights": res["nights"],
            "status": res["status"],
            "payment_status": res.get("paymentStatus", "unknown"),
            "reservation_agreement": res.get("reservationAgreement", "unknown"),
            "door_code": res.get("doorCode"),
            "is_instant_booked": bool(res.get("isInstantBooked", 0)),
            "number_of_guests": res.get("numberOfGuests", 1),
            "adults": res.get("adults"),
            "children": res.get("children"),
            "infants": res.get("infants"),
            "pets": res.get("pets"),
            "channel_type": normalize_channel_type(res.get("channelId")),
            "source_type": "api_pull",
            "pms_id": pms_id,
            "pms_type": "hostaway",
            "pms_meta": res,
            "primary_guest_id": guest_id if res["status"] in real_statuses else None,
            "webhook_id": None
        })

    return reservations

def insert_reservations(conn, reservations: List[Dict]) -> Dict[str, UUID]:
    if not reservations:
        logger.info("No reservations to insert.")
        return {}

    columns = [
        "listing_id", "reservation_date", "check_in_date", "check_out_date", "check_in_time", "check_out_time",
        "nights", "status", "payment_status", "reservation_agreement", "door_code",
        "is_instant_booked", "number_of_guests", "adults", "children", "infants", "pets",
        "pms_id", "pms_type", "pms_meta", "source_type", "primary_guest_id"
    ]

    sql = f"""
    INSERT INTO reservations ({', '.join(columns)})
    VALUES %s
    ON CONFLICT (listing_id, reservation_date, primary_guest_id) DO UPDATE
    SET
        check_in_date = EXCLUDED.check_in_date,
        check_out_date = EXCLUDED.check_out_date,
        check_in_time = EXCLUDED.check_in_time,
        check_out_time = EXCLUDED.check_out_time,
        nights = EXCLUDED.nights,
        status = EXCLUDED.status,
        payment_status = EXCLUDED.payment_status,
        reservation_agreement = EXCLUDED.reservation_agreement,
        door_code = EXCLUDED.door_code,
        is_instant_booked = EXCLUDED.is_instant_booked,
        number_of_guests = EXCLUDED.number_of_guests,
        adults = EXCLUDED.adults,
        children = EXCLUDED.children,
        infants = EXCLUDED.infants,
        pets = EXCLUDED.pets,
        pms_type = EXCLUDED.pms_type,
        pms_meta = EXCLUDED.pms_meta
    WHERE (
        reservations.check_in_date IS DISTINCT FROM EXCLUDED.check_in_date OR
        reservations.check_out_date IS DISTINCT FROM EXCLUDED.check_out_date OR
        reservations.check_in_time IS DISTINCT FROM EXCLUDED.check_in_time OR
        reservations.check_out_time IS DISTINCT FROM EXCLUDED.check_out_time OR
        reservations.nights IS DISTINCT FROM EXCLUDED.nights OR
        reservations.status IS DISTINCT FROM EXCLUDED.status OR
        reservations.payment_status IS DISTINCT FROM EXCLUDED.payment_status OR
        reservations.reservation_agreement IS DISTINCT FROM EXCLUDED.reservation_agreement OR
        reservations.door_code IS DISTINCT FROM EXCLUDED.door_code OR
        reservations.is_instant_booked IS DISTINCT FROM EXCLUDED.is_instant_booked OR
        reservations.number_of_guests IS DISTINCT FROM EXCLUDED.number_of_guests OR
        reservations.adults IS DISTINCT FROM EXCLUDED.adults OR
        reservations.children IS DISTINCT FROM EXCLUDED.children OR
        reservations.infants IS DISTINCT FROM EXCLUDED.infants OR
        reservations.pets IS DISTINCT FROM EXCLUDED.pets OR
        reservations.pms_type IS DISTINCT FROM EXCLUDED.pms_type OR
        reservations.pms_meta IS DISTINCT FROM EXCLUDED.pms_meta
    )
    """

    values = [
        [json.dumps(r.get(col)) if isinstance(r.get(col), dict) else r.get(col) for col in columns]
        for r in reservations
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, page_size=100)

        cur.execute(
            """
            SELECT reservation_id,
                listing_id,
                reservation_date,
                primary_guest_id,
                (pms_meta->>'id')::bigint AS hostaway_reservation_id,
                (pms_meta->>'listingMapId')::bigint AS hostaway_listing_id
            FROM reservations
            WHERE pms_id = %s
            """,
            (reservations[0]["pms_id"],)
        )
        rows = cur.fetchall()

    conn.commit()

    return {
        (
            r[5],  # hostaway_listing_id → position 0 in the key tuple
            r[4],  # hostaway_reservation_id → position 1
            r[1],  # listing_id → position 2
            r[2],  # reservation_date → position 3
            r[3],  # primary_guest_id → position 4
        ): r[0]  # reservation_id
        for r in rows
    }

def insert_reservation_guests(conn, reservation_id_map: Dict[str, UUID]):
    if not reservation_id_map:
        logger.info("No reservation guests to insert.")
        return

    values = []
    for (_, _, _, _, primary_guest_id), reservation_id in reservation_id_map.items():
        if primary_guest_id is None:
            continue
        values.append((str(reservation_id), str(primary_guest_id), True))

    if not values:
        logger.info("No valid reservation_guest records to insert.")
        return

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO reservation_guests (reservation_id, guest_id, is_primary_guest)
            VALUES %s
            ON CONFLICT DO NOTHING
            """,
            values,
            page_size=100
        )

    conn.commit()

def normalize_reservation_messages(
    raw_messages: List[Dict[str, Any]],
    pms_id: UUID,
    reservation_id_map: Dict[Tuple[int, int, UUID, datetime.date, UUID], UUID]
) -> List[Tuple[UUID, int, datetime, str, Dict[str, Any]]]:
    # Build lookups from full 5-part key
    lookup = {
        (h_listing_id, h_res_id): (reservation_id, listing_id)
        for (h_listing_id, h_res_id, listing_id, _, _), reservation_id in reservation_id_map.items()
    }

    values = []

    for msg in raw_messages:
        key = (int(msg["listingMapId"]), int(msg["reservationId"]))
        if key not in lookup:
            logging.warning(f"Skipping message: no reservation match for {key}")
            continue

        reservation_id, listing_id = lookup[key]
        sent_ts = (
            msg.get("sentChannelDate")
            or msg.get("date")
            or msg.get("insertedOn")
            or msg.get("updatedOn")
        )        

        values.append((
            reservation_id, 
            listing_id, 
            normalize_channel_type(msg.get("channelId")),   # channel_type
            'api_pull',                                     # source_type
            pms_id,
            psycopg2.extras.Json(msg),                      # pms_meta
            'hostaway',                                     # pms_type
            msg.get("body", "").strip(),                    # message
            bool(msg.get("isIncoming", True)),              # is_incoming
            date_parser.parse(sent_ts)                      # sent_At
        ))

    return values

def insert_reservation_messages(
    conn,
    values: List[tuple]  # (conversation_id, listing_id, reservation_id, pms_meta, pms_id)
) -> None:
    if not values:
        return

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO reservation_messages (
                reservation_id,
                listing_id,
                channel_type,
                source_type,
                pms_id,
                pms_meta,
                pms_type,
                message,
                is_incoming,
                sent_at
            )
            VALUES %s
            ON CONFLICT (reservation_id, listing_id, sent_at) DO NOTHING
            """,
            values,
            page_size=100
        )

    conn.commit()

# === MAIN ===
def run():
    token = get_access_token()
    pms_id = get_pms_id()

    raw_listings = fetch_data("listings", token)
    normalized_listings = normalize_listings(raw_listings, pms_id)

    raw_reservations = fetch_data("reservations", token)
    normalized_guests = normalize_guests(raw_reservations, pms_id)

    with psycopg2.connect(POSTGRES_URL) as conn:
        listing_id_map = insert_listings(conn, normalized_listings)
        logger.info("Upserted listings.")

        guest_id_map = insert_guests(conn, normalized_guests)
        logger.info("Upserted guests.")

        normalized_reservations = normalize_reservations(
            raw_reservations=raw_reservations,
            pms_id=pms_id,
            listing_id_map=listing_id_map,
            guest_id_map=guest_id_map
        )

        reservation_id_map = insert_reservations(conn, normalized_reservations)
        logger.info("Upserted reservations.")

        insert_reservation_guests(conn, reservation_id_map)
        logger.info("Upserted reservation_guests.")

        raw_conversations = fetch_data("conversations", token)
        raw_messages = fetch_conversation_messages(raw_conversations, token)
        normalized_messages = normalize_reservation_messages(
            raw_messages=raw_messages,
            pms_id=pms_id,
            reservation_id_map=reservation_id_map
        )
        insert_reservation_messages(conn, normalized_messages)
        logger.info("Inserted reservation messages.")

if __name__ == '__main__':
    run()

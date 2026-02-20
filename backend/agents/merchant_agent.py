"""
Merchant Agent - Travel catalog and cart builder
Handles intent mandates and generates travel packages
"""

import json
import os
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_TIMEOUT,
    MERCHANT_ID,
    MERCHANT_NAME,
    MERCHANT_AGENT_URL,
)
from ap2_types import (
    IntentMandate,
    TravelPackage,
    Flight,
    Hotel,
    Activity,
)
from utils import (
    get_logger,
    log_mandate_event,
    log_llm_call,
    sign_mandate,
    generate_merchant_signature,
    hash_cart,
)

logger = get_logger("MerchantAgent")


class MerchantAgent:
    """
    Travel merchant agent for catalog search and cart generation.

    Responsibilities:
    1. Parse IntentMandate from ShoppingAgent
    2. Use LLM to generate realistic travel options
    3. Create 3 tier packages (value/recommended/premium)
    4. Sign cart with merchant signature
    """

    def __init__(self):
        self.merchant_id = MERCHANT_ID
        self.merchant_name = MERCHANT_NAME

    async def process_intent_mandate(
        self,
        intent_mandate: Dict[str, Any],
        shopping_agent_id: str,
        risk_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an intent mandate and generate travel packages.
        """
        logger.info(f"Processing IntentMandate: {intent_mandate.get('mandate_id', 'unknown')}")
        log_mandate_event(logger, "RECEIVED", "IntentMandate", intent_mandate.get("mandate_id", ""))

        # Validate the mandate
        if not self._validate_intent_mandate(intent_mandate):
            return {"error": "Invalid intent mandate"}

        # Extract shopping intent
        shopping_intent = intent_mandate.get("shopping_intent", {})

        # Generate travel packages using LLM
        packages = await self._generate_travel_packages(
            shopping_intent=shopping_intent,
            natural_description=intent_mandate.get("natural_language_description", ""),
            spending_limits=intent_mandate.get("spending_limits", {})
        )

        # Add merchant signatures to each package
        for package in packages:
            package_dict = package.model_dump()
            cart_hash = hash_cart(self._package_to_line_items(package_dict))
            package_dict["merchant_signature"] = generate_merchant_signature(
                self.merchant_id,
                cart_hash
            )

        logger.info(f"Generated {len(packages)} travel packages")

        return {
            "packages": [p.model_dump() for p in packages],
            "merchant_id": self.merchant_id,
            "merchant_name": self.merchant_name,
            "merchant_agent_url": MERCHANT_AGENT_URL,
            "intent_mandate_id": intent_mandate.get("mandate_id")
        }

    def _validate_intent_mandate(self, mandate: Dict[str, Any]) -> bool:
        """Validate the intent mandate structure and expiry."""
        required_fields = ["mandate_id", "shopping_intent", "spending_limits"]

        for field in required_fields:
            if field not in mandate:
                logger.warning(f"Missing required field: {field}")
                return False

        # Check expiry - be lenient with timezone handling
        expires_at = mandate.get("expires_at")
        if expires_at:
            try:
                # Parse expiry time
                if expires_at.endswith("Z"):
                    expiry_str = expires_at.replace("Z", "+00:00")
                else:
                    expiry_str = expires_at

                expiry = datetime.fromisoformat(expiry_str)

                # Compare with UTC now if expiry is timezone-aware
                if expiry.tzinfo is not None:
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                else:
                    now = datetime.now()

                if expiry < now:
                    logger.warning(f"Intent mandate has expired (expiry: {expiry}, now: {now})")
                    return False
            except Exception as e:
                logger.warning(f"Could not parse expiry: {e}")
                # Don't fail validation on parse errors

        return True

    async def _generate_travel_packages(
        self,
        shopping_intent: Dict[str, Any],
        natural_description: str,
        spending_limits: Dict[str, Any]
    ) -> List[TravelPackage]:
        """Generate travel packages - uses mock data for speed, LLM optional."""

        destination = shopping_intent.get("destination") or "Dubai"
        origin = shopping_intent.get("origin") or "New York"
        travel_dates = shopping_intent.get("travel_dates") or {}
        travelers = shopping_intent.get("travelers") or 2
        budget = shopping_intent.get("budget_usd") or 8000
        cabin_class = shopping_intent.get("cabin_class") or "economy"
        preferences = shopping_intent.get("preferences") or []

        start_date = travel_dates.get("start") or (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d")
        end_date = travel_dates.get("end") or (datetime.now() + timedelta(days=26)).strftime("%Y-%m-%d")

        # Always use LLM for package generation
        logger.info(f"Generating LLM packages for {destination} ({travelers} travelers, ${budget} budget)")

        # Calculate nights
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            nights = (end_dt - start_dt).days
        except:
            nights = 5

        prompt = f"""You are a travel merchant AI. Generate 3 realistic travel package options for:
- Destination: {destination}
- Origin: {origin}
- Travel dates: {start_date} to {end_date} ({nights} nights)
- Travelers: {travelers}
- Budget: ${budget} USD
- Class preference: {cabin_class}
- Preferences: {preferences}

Generate exactly 3 packages (value, recommended, premium) as JSON:
{{
  "packages": [
    {{
      "tier": "value",
      "flights": [
        {{
          "flight_id": "unique_id",
          "airline": "airline name",
          "flight_number": "XX-123",
          "departure_city": "{origin}",
          "arrival_city": "{destination}",
          "departure_time": "datetime",
          "arrival_time": "datetime",
          "cabin_class": "{cabin_class}",
          "price_per_person_usd": number,
          "refundable": true
        }}
      ],
      "hotels": [
        {{
          "hotel_id": "unique_id",
          "name": "hotel name",
          "location": "{destination}",
          "star_rating": 4,
          "price_per_night_usd": number,
          "nights": {nights},
          "check_in": "{start_date}",
          "check_out": "{end_date}",
          "room_type": "Deluxe Room",
          "refundable": true
        }}
      ],
      "activities": [
        {{
          "activity_id": "unique_id",
          "name": "activity name",
          "description": "brief description",
          "price_per_person_usd": number,
          "duration": "3 hours",
          "included": ["item1", "item2"]
        }}
      ],
      "total_usd": number,
      "description": "brief package description"
    }}
  ]
}}

Requirements:
- Value package: ~60-70% of budget, 3-4 star hotels, fewer activities
- Recommended package: ~80-90% of budget, 5-star hotels, more activities
- Premium package: at or slightly above budget, luxury options, VIP experiences
- Include realistic airline names for the route
- Include real hotel names in {destination}
- Include popular tourist activities
- Make sure prices are realistic

Return ONLY the JSON object starting with {{ - no thinking, no explanation, no markdown."""

        try:
            start_time = time.time()

            async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": [{"role": "user", "content": "/no_think\n" + prompt}],
                        "temperature": 0.3
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            duration = time.time() - start_time

            log_llm_call(
                logger,
                model=OPENROUTER_MODEL,
                prompt_preview=prompt[:300],
                response_preview=response_text[:300],
                duration_seconds=duration
            )

            # Extract JSON from response
            json_text = response_text

            # Remove thinking tags if present (some LLMs add these)
            if "<think>" in json_text:
                # Extract content after </think>
                think_end = json_text.find("</think>")
                if think_end != -1:
                    json_text = json_text[think_end + 8:]

            # Try code block extraction
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]

            # If no code blocks, try to find JSON object directly
            if not json_text.strip().startswith("{"):
                # Find first { and last }
                first_brace = json_text.find("{")
                last_brace = json_text.rfind("}")
                if first_brace != -1 and last_brace != -1:
                    json_text = json_text[first_brace:last_brace + 1]

            json_text = json_text.strip()

            if not json_text:
                raise json.JSONDecodeError("Empty JSON after extraction", "", 0)

            # Try to fix common JSON issues from LLM output
            json_text = self._repair_json(json_text)

            data = json.loads(json_text)

            packages = []
            for pkg_data in data.get("packages", []):
                pkg_data["package_id"] = f"pkg_{uuid.uuid4().hex[:8]}"
                pkg_data["travelers"] = travelers
                pkg_data["nights"] = nights

                # Ensure all sub-items have IDs
                for flight in pkg_data.get("flights", []):
                    if "flight_id" not in flight:
                        flight["flight_id"] = f"fl_{uuid.uuid4().hex[:6]}"

                for hotel in pkg_data.get("hotels", []):
                    if "hotel_id" not in hotel:
                        hotel["hotel_id"] = f"ht_{uuid.uuid4().hex[:6]}"

                for activity in pkg_data.get("activities", []):
                    if "activity_id" not in activity:
                        activity["activity_id"] = f"ac_{uuid.uuid4().hex[:6]}"

                packages.append(TravelPackage(**pkg_data))

            return packages

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response (first 500 chars): {response_text[:500] if 'response_text' in dir() else 'N/A'}")
            logger.info("Retrying with simplified prompt...")
            # Retry with a simpler prompt
            return await self._generate_packages_simple(
                destination, origin, start_date, end_date, nights, travelers, budget, cabin_class
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            logger.info("Retrying with simplified prompt...")
            return await self._generate_packages_simple(
                destination, origin, start_date, end_date, nights, travelers, budget, cabin_class
            )

    async def _generate_packages_simple(
        self,
        destination: str,
        origin: str,
        start_date: str,
        end_date: str,
        nights: int,
        travelers: int,
        budget: float,
        cabin_class: str
    ) -> List[TravelPackage]:
        """Generate packages with a simpler, more reliable prompt."""

        prompt = f"""Generate 3 travel packages as JSON for {travelers} travelers going from {origin} to {destination} for {nights} nights ({start_date} to {end_date}). Budget: ${budget}.

Return ONLY this JSON structure, no other text:
{{"packages":[
{{"tier":"value","flights":[{{"airline":"Economy Air","flight_number":"EA101","departure_city":"{origin}","arrival_city":"{destination}","departure_time":"{start_date}T08:00:00","arrival_time":"{start_date}T14:00:00","cabin_class":"{cabin_class}","price_per_person_usd":400,"refundable":true}}],"hotels":[{{"name":"City Inn","location":"{destination}","star_rating":3,"price_per_night_usd":100,"nights":{nights},"check_in":"{start_date}","check_out":"{end_date}","room_type":"Standard","refundable":true}}],"activities":[{{"name":"City Tour","description":"Sightseeing","price_per_person_usd":50,"duration":"3 hours","included":["Guide"]}}],"total_usd":{int(budget*0.6)},"description":"Budget-friendly option"}},
{{"tier":"recommended","flights":[{{"airline":"Premium Air","flight_number":"PA202","departure_city":"{origin}","arrival_city":"{destination}","departure_time":"{start_date}T10:00:00","arrival_time":"{start_date}T16:00:00","cabin_class":"{cabin_class}","price_per_person_usd":600,"refundable":true}}],"hotels":[{{"name":"Grand Hotel","location":"{destination}","star_rating":4,"price_per_night_usd":200,"nights":{nights},"check_in":"{start_date}","check_out":"{end_date}","room_type":"Deluxe","refundable":true}}],"activities":[{{"name":"Premium Tour","description":"VIP Experience","price_per_person_usd":100,"duration":"5 hours","included":["Guide","Lunch"]}}],"total_usd":{int(budget*0.85)},"description":"Best value package"}},
{{"tier":"premium","flights":[{{"airline":"Luxury Airways","flight_number":"LA303","departure_city":"{origin}","arrival_city":"{destination}","departure_time":"{start_date}T12:00:00","arrival_time":"{start_date}T18:00:00","cabin_class":"business","price_per_person_usd":900,"refundable":true}}],"hotels":[{{"name":"Luxury Resort","location":"{destination}","star_rating":5,"price_per_night_usd":400,"nights":{nights},"check_in":"{start_date}","check_out":"{end_date}","room_type":"Suite","refundable":true}}],"activities":[{{"name":"Exclusive Tour","description":"Private guide","price_per_person_usd":200,"duration":"Full day","included":["Guide","Meals","Transport"]}}],"total_usd":{int(budget*1.1)},"description":"Luxury experience"}}
]}}"""

        try:
            async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": [{"role": "user", "content": "/no_think\n" + prompt}],
                        "temperature": 0.1
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract JSON same as main method
            json_text = response_text
            if "<think>" in json_text:
                think_end = json_text.find("</think>")
                if think_end != -1:
                    json_text = json_text[think_end + 8:]

            if not json_text.strip().startswith("{"):
                first_brace = json_text.find("{")
                last_brace = json_text.rfind("}")
                if first_brace != -1 and last_brace != -1:
                    json_text = json_text[first_brace:last_brace + 1]

            json_text = self._repair_json(json_text.strip())
            data = json.loads(json_text)

            packages = []
            for pkg_data in data.get("packages", []):
                pkg_data["package_id"] = f"pkg_{uuid.uuid4().hex[:8]}"
                pkg_data["travelers"] = travelers
                pkg_data["nights"] = nights

                for flight in pkg_data.get("flights", []):
                    if "flight_id" not in flight:
                        flight["flight_id"] = f"fl_{uuid.uuid4().hex[:6]}"
                for hotel in pkg_data.get("hotels", []):
                    if "hotel_id" not in hotel:
                        hotel["hotel_id"] = f"ht_{uuid.uuid4().hex[:6]}"
                for activity in pkg_data.get("activities", []):
                    if "activity_id" not in activity:
                        activity["activity_id"] = f"ac_{uuid.uuid4().hex[:6]}"

                packages.append(TravelPackage(**pkg_data))

            logger.info(f"Generated {len(packages)} packages with simplified LLM prompt")
            return packages

        except Exception as e:
            logger.error(f"Simplified LLM also failed: {e}, using hardcoded packages")
            # Last resort - return hardcoded packages (still LLM-generated structure)
            return self._generate_hardcoded_packages(
                destination, origin, start_date, end_date, nights, travelers, budget, cabin_class
            )

    def _generate_hardcoded_packages(
        self,
        destination: str,
        origin: str,
        start_date: str,
        end_date: str,
        nights: int,
        travelers: int,
        budget: float,
        cabin_class: str
    ) -> List[TravelPackage]:
        """Generate hardcoded packages as last resort."""
        logger.info("Using hardcoded package structure")

        packages = []
        tiers = [
            ("value", 0.6, 3, "Budget-friendly package"),
            ("recommended", 0.85, 4, "Best value - our top pick"),
            ("premium", 1.1, 5, "Luxury experience")
        ]

        for tier, price_mult, stars, desc in tiers:
            pkg = TravelPackage(
                package_id=f"pkg_{uuid.uuid4().hex[:8]}",
                tier=tier,
                flights=[Flight(
                    flight_id=f"fl_{uuid.uuid4().hex[:6]}",
                    airline="Travel Airways",
                    flight_number=f"TA{100 + len(packages)}",
                    departure_city=origin,
                    arrival_city=destination,
                    departure_time=f"{start_date}T10:00:00",
                    arrival_time=f"{start_date}T16:00:00",
                    cabin_class=cabin_class if tier != "premium" else "business",
                    price_per_person_usd=int(400 * price_mult),
                    refundable=True
                )],
                hotels=[Hotel(
                    hotel_id=f"ht_{uuid.uuid4().hex[:6]}",
                    name=f"{destination} {'Inn' if tier == 'value' else 'Grand Hotel' if tier == 'recommended' else 'Luxury Resort'}",
                    location=destination,
                    star_rating=stars,
                    price_per_night_usd=int(150 * price_mult),
                    nights=nights,
                    check_in=start_date,
                    check_out=end_date,
                    room_type="Standard" if tier == "value" else "Deluxe" if tier == "recommended" else "Suite",
                    refundable=True
                )],
                activities=[Activity(
                    activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                    name=f"{destination} Tour",
                    description="Explore the city highlights",
                    price_per_person_usd=int(50 * price_mult),
                    duration="4 hours",
                    included=["Guide", "Water"] if tier == "value" else ["Guide", "Lunch", "Transport"]
                )],
                total_usd=int(budget * price_mult),
                travelers=travelers,
                nights=nights,
                description=desc
            )
            packages.append(pkg)

        return packages

    def _repair_json(self, json_text: str) -> str:
        """Attempt to repair common JSON issues from LLM output."""
        import re

        text = json_text

        # Remove trailing commas before ] or }
        text = re.sub(r',(\s*[\]\}])', r'\1', text)

        # Fix missing commas between objects/arrays
        text = re.sub(r'(\})\s*(\{)', r'\1,\2', text)
        text = re.sub(r'(\])\s*(\[)', r'\1,\2', text)

        # Fix missing commas after string values
        text = re.sub(r'(")\s*\n\s*(")', r'\1,\n\2', text)

        # Remove any text after the final closing brace
        last_brace = text.rfind('}')
        if last_brace != -1:
            text = text[:last_brace + 1]

        # Ensure the JSON starts with {
        first_brace = text.find('{')
        if first_brace > 0:
            text = text[first_brace:]

        return text

    def _generate_mock_packages(
        self,
        destination: str,
        origin: str,
        start_date: str,
        end_date: str,
        nights: int,
        travelers: int,
        budget: float,
        cabin_class: str
    ) -> List[TravelPackage]:
        """Generate mock travel packages when LLM is unavailable."""

        logger.info("Using mock package generator")

        # Value package - ~65% of budget
        value_flight_price = 450 if cabin_class == "economy" else 700
        value_hotel_price = 150
        value_activities = [
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="City Walking Tour",
                description="Explore the city's highlights on foot",
                price_per_person_usd=45,
                duration="3 hours",
                included=["Guide", "Water"]
            ),
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="Local Market Visit",
                description="Experience local culture and cuisine",
                price_per_person_usd=35,
                duration="2 hours",
                included=["Guide", "Snacks"]
            )
        ]

        value_total = (value_flight_price * travelers * 2) + (value_hotel_price * nights) + sum(a.price_per_person_usd * travelers for a in value_activities)

        value_package = TravelPackage(
            tier="value",
            travelers=travelers,
            nights=nights,
            flights=[
                Flight(
                    flight_id=f"fl_{uuid.uuid4().hex[:6]}",
                    airline="Emirates",
                    flight_number="EK-512",
                    departure_city=origin,
                    arrival_city=destination,
                    departure_time=f"{start_date}T08:00:00",
                    arrival_time=f"{start_date}T20:00:00",
                    cabin_class=cabin_class,
                    price_per_person_usd=value_flight_price,
                    refundable=True
                ),
                Flight(
                    flight_id=f"fl_{uuid.uuid4().hex[:6]}",
                    airline="Emirates",
                    flight_number="EK-513",
                    departure_city=destination,
                    arrival_city=origin,
                    departure_time=f"{end_date}T22:00:00",
                    arrival_time=f"{end_date}T08:00:00+1",
                    cabin_class=cabin_class,
                    price_per_person_usd=value_flight_price,
                    refundable=True
                )
            ],
            hotels=[
                Hotel(
                    hotel_id=f"ht_{uuid.uuid4().hex[:6]}",
                    name="Marriott City Hotel",
                    location=destination,
                    star_rating=4,
                    price_per_night_usd=value_hotel_price,
                    nights=nights,
                    check_in=start_date,
                    check_out=end_date,
                    room_type="Deluxe Room",
                    refundable=True
                )
            ],
            activities=value_activities,
            total_usd=value_total,
            description=f"Value {nights}-night {destination} getaway with 4-star accommodation"
        )

        # Recommended package - ~85% of budget
        rec_flight_price = 650 if cabin_class == "economy" else 950
        rec_hotel_price = 250
        rec_activities = [
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="Sunset Dinner Cruise",
                description="Romantic dinner cruise with stunning views",
                price_per_person_usd=89,
                duration="3 hours",
                included=["Dinner", "Drinks", "Entertainment"]
            ),
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="Heritage City Tour",
                description="Private guided tour of historical sites",
                price_per_person_usd=65,
                duration="4 hours",
                included=["Guide", "Entrance fees", "Lunch"]
            ),
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="Desert Safari",
                description="Adventure in the dunes with BBQ dinner",
                price_per_person_usd=75,
                duration="6 hours",
                included=["Transport", "Dinner", "Entertainment"]
            )
        ]

        rec_total = (rec_flight_price * travelers * 2) + (rec_hotel_price * nights) + sum(a.price_per_person_usd * travelers for a in rec_activities)

        recommended_package = TravelPackage(
            tier="recommended",
            travelers=travelers,
            nights=nights,
            flights=[
                Flight(
                    flight_id=f"fl_{uuid.uuid4().hex[:6]}",
                    airline="Emirates",
                    flight_number="EK-784",
                    departure_city=origin,
                    arrival_city=destination,
                    departure_time=f"{start_date}T10:00:00",
                    arrival_time=f"{start_date}T22:00:00",
                    cabin_class="business" if cabin_class != "economy" else cabin_class,
                    price_per_person_usd=rec_flight_price,
                    refundable=True
                ),
                Flight(
                    flight_id=f"fl_{uuid.uuid4().hex[:6]}",
                    airline="Emirates",
                    flight_number="EK-785",
                    departure_city=destination,
                    arrival_city=origin,
                    departure_time=f"{end_date}T23:30:00",
                    arrival_time=f"{end_date}T07:00:00+1",
                    cabin_class="business" if cabin_class != "economy" else cabin_class,
                    price_per_person_usd=rec_flight_price,
                    refundable=True
                )
            ],
            hotels=[
                Hotel(
                    hotel_id=f"ht_{uuid.uuid4().hex[:6]}",
                    name="Grand Hyatt",
                    location=destination,
                    star_rating=5,
                    price_per_night_usd=rec_hotel_price,
                    nights=nights,
                    check_in=start_date,
                    check_out=end_date,
                    room_type="Grand Suite",
                    refundable=True
                )
            ],
            activities=rec_activities,
            total_usd=rec_total,
            description=f"Recommended {nights}-night luxury {destination} experience with 5-star resort"
        )

        # Premium package - at/above budget
        prem_flight_price = 1100
        prem_hotel_price = 450
        prem_activities = [
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="Private Yacht Charter",
                description="Full-day private yacht experience",
                price_per_person_usd=350,
                duration="8 hours",
                included=["Gourmet lunch", "Water sports", "Crew"]
            ),
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="VIP Desert Experience",
                description="Exclusive desert camp with fine dining",
                price_per_person_usd=250,
                duration="5 hours",
                included=["Fine dining", "Private camp", "Entertainment"]
            ),
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="Helicopter City Tour",
                description="Aerial tour of the city landmarks",
                price_per_person_usd=400,
                duration="45 minutes",
                included=["Champagne", "Photos"]
            ),
            Activity(
                activity_id=f"ac_{uuid.uuid4().hex[:6]}",
                name="Spa Day at Palace",
                description="Full day of luxury spa treatments",
                price_per_person_usd=200,
                duration="6 hours",
                included=["Treatments", "Lunch", "Pool access"]
            )
        ]

        prem_total = (prem_flight_price * travelers * 2) + (prem_hotel_price * nights) + sum(a.price_per_person_usd * travelers for a in prem_activities)

        premium_package = TravelPackage(
            tier="premium",
            travelers=travelers,
            nights=nights,
            flights=[
                Flight(
                    flight_id=f"fl_{uuid.uuid4().hex[:6]}",
                    airline="Singapore Airlines",
                    flight_number="SQ-891",
                    departure_city=origin,
                    arrival_city=destination,
                    departure_time=f"{start_date}T09:00:00",
                    arrival_time=f"{start_date}T21:00:00",
                    cabin_class="first",
                    price_per_person_usd=prem_flight_price,
                    refundable=True
                ),
                Flight(
                    flight_id=f"fl_{uuid.uuid4().hex[:6]}",
                    airline="Singapore Airlines",
                    flight_number="SQ-892",
                    departure_city=destination,
                    arrival_city=origin,
                    departure_time=f"{end_date}T23:00:00",
                    arrival_time=f"{end_date}T09:00:00+1",
                    cabin_class="first",
                    price_per_person_usd=prem_flight_price,
                    refundable=True
                )
            ],
            hotels=[
                Hotel(
                    hotel_id=f"ht_{uuid.uuid4().hex[:6]}",
                    name="Burj Al Arab",
                    location=destination,
                    star_rating=5,
                    price_per_night_usd=prem_hotel_price,
                    nights=nights,
                    check_in=start_date,
                    check_out=end_date,
                    room_type="Royal Suite",
                    refundable=True
                )
            ],
            activities=prem_activities,
            total_usd=prem_total,
            description=f"Ultimate {nights}-night VIP {destination} experience with iconic luxury"
        )

        return [value_package, recommended_package, premium_package]

    def _package_to_line_items(self, package: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert a package to line items for hashing."""
        items = []
        travelers = package.get("travelers", 1)

        for flight in package.get("flights", []):
            items.append({
                "item_type": "flight",
                "item_id": flight.get("flight_id"),
                "price": flight.get("price_per_person_usd", 0) * travelers
            })

        for hotel in package.get("hotels", []):
            items.append({
                "item_type": "hotel",
                "item_id": hotel.get("hotel_id"),
                "price": hotel.get("price_per_night_usd", 0) * hotel.get("nights", 1)
            })

        for activity in package.get("activities", []):
            items.append({
                "item_type": "activity",
                "item_id": activity.get("activity_id"),
                "price": activity.get("price_per_person_usd", 0) * travelers
            })

        return items


# Singleton instance
merchant_agent = MerchantAgent()

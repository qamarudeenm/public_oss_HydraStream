# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Clickstream Traffic Simulator
Generates configurable numbers of mock users with randomized ecommerce journeys.

Usage (standalone):
    python simulate.py --users 50 --collector-url http://localhost:5000/events

Environment Variables:
    SIMULATOR_USERS          Number of concurrent users (default: 20)
    SIMULATOR_COLLECTOR_URL  Collector endpoint (default: http://collector:5000/events)
    SIMULATOR_PACE           Delay between user actions in seconds (default: 0.3)
"""

import asyncio
import random
import uuid
import json
import os
import sys
import time
import argparse
import logging
from datetime import datetime

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("simulator")

# ─── Product Catalog (mirrors website/main.js) ───
PRODUCTS = [
    {"id": "prod_001", "name": "Aero-Flow Runners",     "price": 189.99},
    {"id": "prod_002", "name": "Nexus Chrono v2",        "price": 449.00},
    {"id": "prod_003", "name": "Zenith ANC Headphones",  "price": 299.50},
]

PAGES = ["home", "cart", "checkout", "status-success", "status-failure"]

# ─── Journey Templates ───
# Each user randomly follows one of these weighted journey types.
# Weights control how likely each journey is.
JOURNEYS = [
    # (weight, name, steps)
    (40, "browser",         ["browse"]),                                                    # just browses, no cart
    (25, "cart_abandoner",   ["browse", "add_to_cart", "browse_more"]),                      # adds to cart, leaves
    (15, "checkout_abandoner", ["browse", "add_to_cart", "checkout_start", "shipping"]),     # starts checkout, leaves
    (10, "successful_buyer", ["browse", "add_to_cart", "checkout_start", "shipping", "pay_success"]),
    ( 5, "failed_buyer",     ["browse", "add_to_cart", "checkout_start", "shipping", "pay_fail"]),
    ( 5, "retry_buyer",      ["browse", "add_to_cart", "checkout_start", "shipping", "pay_fail", "retry", "pay_success"]),
]

JOURNEY_WEIGHTS = [j[0] for j in JOURNEYS]
JOURNEY_NAMES   = [j[1] for j in JOURNEYS]
JOURNEY_STEPS   = [j[2] for j in JOURNEYS]


class MockUser:
    """Simulates a single user session with a randomized journey."""

    def __init__(self, collector_url: str, pace: float):
        self.user_id = f"user_{uuid.uuid4().hex[:10]}"
        self.session_id = f"sess_{uuid.uuid4().hex[:10]}"
        self.collector_url = collector_url
        self.pace = pace
        self.cart = []

        journey_idx = random.choices(range(len(JOURNEYS)), weights=JOURNEY_WEIGHTS, k=1)[0]
        self.journey_name = JOURNEY_NAMES[journey_idx]
        self.steps = JOURNEY_STEPS[journey_idx]

    async def send_event(self, client: httpx.AsyncClient, event_type: str, data: dict = None, 
                         product_id: str = None, element_id: str = None, element_text: str = None):
        payload = {
            "event_type": event_type,
            "page_url": f"http://localhost:3000/#{event_type}",
            "user_id": self.user_id,
            "session_id": self.session_id,
            "product_id": product_id,
            "element_id": element_id,
            "element_text": element_text,
            "data": data or {},
            "timestamp": datetime.now().isoformat(timespec='milliseconds'),
        }
        try:
            resp = await client.post(self.collector_url, json=payload, timeout=5.0)
            if resp.status_code == 200:
                logger.debug(f"  [{self.user_id}] {event_type}")
            else:
                logger.warning(f"  [{self.user_id}] {event_type} → HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"  [{self.user_id}] {event_type} → ERROR: {repr(e)}")

    async def run(self, client: httpx.AsyncClient):
        logger.info(f"👤 {self.user_id} starting journey: {self.journey_name} ({len(self.steps)} steps)")

        for step in self.steps:
            await asyncio.sleep(random.uniform(self.pace * 0.5, self.pace * 1.5))

            if step == "browse":
                # View homepage
                await self.send_event(client, "page_view", {"page": "home"})
                # Click on 1-3 products
                for _ in range(random.randint(1, 3)):
                    product = random.choice(PRODUCTS)
                    await self.send_event(client, "click", {
                        "classes": "product-card"
                    }, element_id=f"product-{product['id']}", element_text=product["name"])
                    await asyncio.sleep(random.uniform(0.1, self.pace))

            elif step == "browse_more":
                # Extra browsing after cart add
                await self.send_event(client, "page_view", {"page": "home"})
                for _ in range(random.randint(1, 2)):
                    product = random.choice(PRODUCTS)
                    await self.send_event(client, "click", {
                        "element_id": f"product-{product['id']}",
                        "element_text": product["name"],
                        "classes": "product-card"
                    })

            elif step == "add_to_cart":
                # Add 1-3 random products
                num_items = random.randint(1, 3)
                for _ in range(num_items):
                    product = random.choice(PRODUCTS)
                    self.cart.append(product)
                    await self.send_event(client, "add_to_cart", {
                        "product_name": product["name"],
                        "price": product["price"]
                    }, product_id=product["id"])
                    await asyncio.sleep(random.uniform(0.05, 0.2))

                # Maybe remove one item
                if len(self.cart) > 1 and random.random() < 0.3:
                    removed = self.cart.pop(random.randint(0, len(self.cart) - 1))
                    await self.send_event(client, "remove_from_cart", {}, product_id=removed["id"])

                # View cart page
                await self.send_event(client, "page_view", {"page": "cart"})

            elif step == "checkout_start":
                total = sum(p["price"] for p in self.cart)
                await self.send_event(client, "checkout_start", {
                    "cart_size": len(self.cart),
                    "total": round(total, 2)
                })
                await self.send_event(client, "page_view", {"page": "checkout"})

            elif step == "shipping":
                await self.send_event(client, "checkout_step", {"step": "payment"})

            elif step == "pay_success":
                total = sum(p["price"] for p in self.cart)
                order_id = f"NX-{random.randint(100000, 999999)}"
                await self.send_event(client, "purchase_success", {
                    "order_id": order_id,
                    "total": round(total, 2)
                })
                await self.send_event(client, "page_view", {"page": "status-success"})
                self.cart = []

            elif step == "pay_fail":
                reasons = ["insufficient_funds", "card_declined", "network_error", "timeout"]
                await self.send_event(client, "purchase_failed", {
                    "reason": random.choice(reasons)
                })
                await self.send_event(client, "page_view", {"page": "status-failure"})

            elif step == "retry":
                await self.send_event(client, "retry_payment", {})
                await self.send_event(client, "page_view", {"page": "checkout"})

        logger.info(f"✅ {self.user_id} finished journey: {self.journey_name}")


async def run_simulation(num_users: int, collector_url: str, pace: float):
    logger.info(f"{'='*60}")
    logger.info(f"🚀 Clickstream Simulator")
    logger.info(f"   Users:     {num_users}")
    logger.info(f"   Collector: {collector_url}")
    logger.info(f"   Pace:      {pace}s between actions")
    logger.info(f"{'='*60}")

    # Wait for collector to be ready
    async with httpx.AsyncClient() as client:
        health_url = collector_url.rsplit("/", 1)[0] + "/health"
        for attempt in range(30):
            try:
                resp = await client.get(health_url, timeout=3.0)
                if resp.status_code == 200:
                    logger.info(f"✅ Collector is ready at {collector_url}")
                    break
            except Exception:
                pass
            logger.info(f"⏳ Waiting for collector... (attempt {attempt + 1}/30)")
            await asyncio.sleep(2)
        else:
            logger.error("❌ Collector not available after 60s. Exiting.")
            sys.exit(1)

    while True:
        # Create and run a batch of users
        users = [MockUser(collector_url, pace) for _ in range(num_users)]
        
        # Log journey distribution for this batch
        journey_counts = {}
        for u in users:
            journey_counts[u.journey_name] = journey_counts.get(u.journey_name, 0) + 1
        logger.info(f"📊 Starting new batch of {num_users} users...")
        
        limits = httpx.Limits(max_connections=num_users + 50, max_keepalive_connections=num_users + 50)
        async with httpx.AsyncClient(limits=limits) as client:
            tasks = [user.run(client) for user in users]
            await asyncio.gather(*tasks)
        
        logger.info(f"😴 Batch complete. Waiting before starting next batch...")
        await asyncio.sleep(pace * 2)


def main():
    parser = argparse.ArgumentParser(description="Clickstream Traffic Simulator")
    parser.add_argument("--users", type=int, default=None, help="Number of simulated users")
    parser.add_argument("--collector-url", type=str, default=None, help="Collector endpoint URL")
    parser.add_argument("--pace", type=float, default=None, help="Seconds between actions")
    args = parser.parse_args()

    num_users     = args.users or int(os.getenv("SIMULATOR_USERS", "20"))
    collector_url = args.collector_url or os.getenv("SIMULATOR_COLLECTOR_URL", "http://collector:5000/events")
    pace          = args.pace or float(os.getenv("SIMULATOR_PACE", "0.3"))

    asyncio.run(run_simulation(num_users, collector_url, pace))


if __name__ == "__main__":
    main()

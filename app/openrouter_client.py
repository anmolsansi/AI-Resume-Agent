import os
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
import logging

BASE_DIR = Path(__file__).resolve().parent.parent
USAGE_FILE = BASE_DIR / "data" / "usage.json"

load_dotenv()

logger = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(self):
        
        logger.error("Initializing OpenRouterClient")
        # keep keys as names; actual values are read from environment when used
        self.keys = [
            "OPENROUTER_KEY_1",
            "OPENROUTER_KEY_2",
            "OPENROUTER_KEY_3",
        ]
        self.daily_limit = int(os.getenv("OPENROUTER_DAILY_CALL_LIMIT", "6"))
        logger.error("Daily call limit set to %s", self.daily_limit)
        self._ensure_usage_file()

    def _ensure_usage_file(self):
        logger.error("Ensuring usage file exists at %s", USAGE_FILE)
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not USAGE_FILE.exists():
            with USAGE_FILE.open("w") as f:
                json.dump({}, f)
            logger.info("Created new usage file: %s", USAGE_FILE)

    def _load_usage(self):
        logger.error("Loading usage from %s", USAGE_FILE)
        with USAGE_FILE.open() as f:
            data = json.load(f)
        logger.error("Loaded usage keys: %s", list(data.keys()))
        return data

    def _save_usage(self, usage):
        logger.error("Saving usage to %s", USAGE_FILE)
        with USAGE_FILE.open("w") as f:
            json.dump(usage, f, indent=2)
        logger.info("Usage saved")

    def _get_today_usage(self):
        usage = self._load_usage()
        today_utc = datetime.now(timezone.utc).date().isoformat()
        logger.error("Today's UTC date: %s", today_utc)
        if today_utc not in usage:
            usage[today_utc] = {}
            logger.error("Initialized usage for date %s", today_utc)
        return usage, today_utc

    def _pick_key(self):
        usage, today = self._get_today_usage()
        logger.error("Picking key for date %s", today)

        for key_name in self.keys:
            key_value = os.getenv(key_name)
            if not key_value:
                logger.error("Env var %s not set, skipping", key_name)
                print(key_name)
                continue

            used = usage[today].get(key_name, 0)
            logger.error("Key %s used %s times today", key_name, used)
            if used < self.daily_limit:
                logger.info("Selected key %s for use (used %s/%s)", key_name, used, self.daily_limit)
                return key_name, key_value, usage, today

        logger.error("No available OpenRouter keys within daily limits")
        raise RuntimeError("No available OpenRouter keys within daily limits")

    def _record_call(self, usage, today, key_name):
        used = usage[today].get(key_name, 0)
        usage[today][key_name] = used + 1
        logger.error("Recording call for key %s: %s -> %s", key_name, used, usage[today][key_name])
        self._save_usage(usage)

    def chat(self, model, messages, temperature=0.2, max_tokens=1024):
        print("Model and Message", model, messages)
        last_error = None
        logger.info("Starting chat request: model=%s, temperature=%s, max_tokens=%s", model, temperature, max_tokens)

        for attempt in range(len(self.keys)):
            key_name, api_key, usage, today = self._pick_key()
            logger.error("Attempt %s: using key %s", attempt + 1, key_name)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://local-resume-agent",
                "X-Title": "resume-agent",
            }

            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                )
            except requests.RequestException as exc:
                logger.exception("RequestException when calling OpenRouter: %s", exc)
                last_error = str(exc)
                # mark this key as exhausted for today
                usage[today][key_name] = self.daily_limit
                self._save_usage(usage)
                continue

            logger.error("OpenRouter response status: %s", resp.status_code)

            if resp.status_code == 200:
                self._record_call(usage, today, key_name)
                data = resp.json()
                print(data)
                logger.info("Chat request succeeded with key %s", key_name)
                return data["choices"][0]["message"]["content"]

            if resp.status_code in (401, 402, 429, 500, 503):
                last_error = f"{resp.status_code} {resp.text}"
                logger.warning("OpenRouter returned %s. Marking key %s as exhausted for today.", resp.status_code, key_name)
                usage[today][key_name] = self.daily_limit
                self._save_usage(usage)
                continue

            resp.raise_for_status()

        logger.error("All keys failed. Last error: %s", last_error)
        raise RuntimeError(f"All keys failed. Last error: {last_error}")

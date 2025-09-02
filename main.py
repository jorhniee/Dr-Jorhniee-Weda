import os
import json
from datetime import datetime, timedelta
import requests

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen

API_KEY = "9c516a61c58bf6a32f823ba000c31dd7"

def safe_user_data_dir():
    """Return a writable path for cache (works on Android & desktop)."""
    try:
        app = App.get_running_app()
        user_dir = app.user_data_dir  # e.g., /data/data/org.test/files/app
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    except Exception:
        # Fallback to current directory
        return "."

def cache_file_path():
    return os.path.join(safe_user_data_dir(), "forecast_cache.json")

def get_location():
    """Auto-detect city via IP. Returns (city, country_code) or (None, None)."""
    try:
        resp = requests.get("http://ip-api.com/json", timeout=10)
        data = resp.json()
        city = data.get("city")
        cc = data.get("countryCode")
        if city and cc:
            return city, cc
    except Exception:
        pass
    return None, None

def fetch_forecast(city, cc):
    """Fetch 3-day forecast summary from OpenWeather 5-day/3h API."""
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city},{cc}&appid={API_KEY}&units=metric&cnt=24"
    r = requests.get(url, timeout=15)
    data = r.json()
    if str(data.get("cod")) != "200":
        raise RuntimeError(data.get("message", "API error"))
    days = []
    # Every 8 entries ~= 24h (3h step) → 3 days
    for i in range(0, min(24, len(data["list"])), 8):
        it = data["list"][i]
        date = it["dt_txt"].split(" ")[0]
        days.append({
            "date": date,
            "temp": round(it["main"]["temp"], 1),
            "desc": it["weather"][0]["description"].capitalize(),
            "humidity": it["main"]["humidity"]
        })
    return {
        "city": city,
        "country": cc,
        "days": days
    }

def save_cache(payload):
    blob = {
        "timestamp": datetime.utcnow().isoformat(),
        "payload": payload
    }
    with open(cache_file_path(), "w", encoding="utf-8") as f:
        json.dump(blob, f)

def load_cache():
    p = cache_file_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            blob = json.load(f)
        ts = datetime.fromisoformat(blob.get("timestamp"))
        if datetime.utcnow() - ts <= timedelta(days=3):
            return blob.get("payload")
    except Exception:
        return None
    return None

class SplashScreen(Screen):
    def on_enter(self):
        # Move to Home after 2.2s
        Clock.schedule_once(lambda dt: self.manager.current = "home", 2.2)

class HomeScreen(Screen):
    def on_enter(self):
        # Auto-refresh on first show
        Clock.schedule_once(lambda dt: self.refresh(), 0.1)

    def _format_forecast_text(self, data, cached=False):
        header = f"[b]📍 {data['city']}, {data['country']}[/b]\n"
        if cached:
            header = "📦 [i]Offline data (cached, valid ≤ 3 days)[/i]\n" + header
        lines = [header, ""]
        for d in data["days"]:
            lines.append(f"📅 {d['date']} — 🌡 {d['temp']}°C • {d['desc']} • 💧 {d['humidity']}%")
        return "\n".join(lines)

    def refresh(self):
        self.ids.result.text = "⏳ Fetching weather…"
        city, cc = get_location()
        if not city:
            cached = load_cache()
            if cached:
                self.ids.result.text = self._format_forecast_text(cached, cached=True) + "\n\n⚠️ Location detect failed."
            else:
                self.ids.result.text = "⚠️ Could not detect location and no cached data available."
            return

        try:
            data = fetch_forecast(city, cc)
            save_cache(data)
            self.ids.result.text = self._format_forecast_text(data)
        except Exception as e:
            cached = load_cache()
            if cached:
                self.ids.result.text = self._format_forecast_text(cached, cached=True) + f"\n\n⚠️ Online fetch failed: {e}"
            else:
                self.ids.result.text = f"⚠️ Online fetch failed and no cached data found: {e}"

class Root(ScreenManager):
    pass

class WeatherApp(App):
    def build(self):
        self.title = "Dr. Jorhniee Weda 🌡️🌤️"
        return Builder.load_file("weather.kv")

if __name__ == "__main__":
    WeatherApp().run()

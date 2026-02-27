from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from requests.auth import HTTPBasicAuth

st.set_page_config(page_title="Factory Throughput Dashboard", layout="wide")

API_BASE = os.getenv("API_BASE", "http://backend:8000")
API_USER = os.getenv("API_USER", "admin")
API_PASSWORD = os.getenv("API_PASSWORD", "changeme")
DEFAULT_CAMERA_IDS = [c.strip() for c in os.getenv("CAMERA_IDS", "cam1").split(",") if c.strip()]
AUTH = HTTPBasicAuth(API_USER, API_PASSWORD)


def api_get(path: str, params=None):
    resp = requests.get(f"{API_BASE}{path}", params=params, auth=AUTH, timeout=15)
    resp.raise_for_status()
    return resp.json()


st.title("Factory Output Vision MVP")

try:
    camera_lookup = api_get("/cameras").get("cameras", [])
    camera_ids = camera_lookup or DEFAULT_CAMERA_IDS
except Exception:
    camera_ids = DEFAULT_CAMERA_IDS

left, right = st.columns([1, 2])
with left:
    camera_id = st.selectbox("Camera", camera_ids)
    window = st.slider("Rolling window (minutes)", 15, 240, 60, 15)
    downtime_minutes = st.slider("Downtime threshold (minutes)", 5, 60, 20, 5)

try:
    status = api_get(f"/status/{camera_id}", {"window_minutes": window, "downtime_minutes": downtime_minutes})
    series = api_get(f"/series/{camera_id}", {"hours": 24})
    evidence = api_get(f"/evidence/{camera_id}", {"limit": 12})
except requests.RequestException as exc:
    st.error(f"Unable to reach backend API: {exc}")
    st.stop()

with right:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Units / Hour", status["units_per_hour"])
    k2.metric("Units Today", status["total_units_today"])
    k3.metric("Current Count", status["current_count"])
    k4.metric("Downtime", "YES" if status["downtime"] else "NO")
    st.caption(f"Last update: {status['last_update']}")

if series:
    df = pd.DataFrame(series)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    st.line_chart(df.set_index("timestamp")[["count"]])
    st.area_chart(df.set_index("timestamp")[["delta"]])
else:
    st.warning("No metrics yet for this camera.")

st.subheader("Evidence Frames")
if not evidence:
    st.info("No evidence frames available.")
else:
    cols = st.columns(3)
    for idx, item in enumerate(evidence):
        with cols[idx % 3]:
            img_resp = requests.get(f"{API_BASE}{item['image_url']}", auth=AUTH, timeout=20)
            if img_resp.status_code == 200:
                ts = datetime.fromisoformat(item["timestamp"])
                st.image(img_resp.content, caption=f"{item['event_type']} @ {ts}")
            else:
                st.error(f"Image load failed for evidence #{item['id']}")

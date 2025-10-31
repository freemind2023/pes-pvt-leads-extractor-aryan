# =============================================================
# PES Pvt Leads Extractor | Free Business Data (OpenStreetMap)
# Made by Free Mind Consultancy | Streamlit App
# =============================================================

import streamlit as st
import requests, json, math, pandas as pd
from io import BytesIO

# ---------- CONFIG ------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
# -------------------------------

# ---- Helper Functions ----
def geocode(city):
    """Get city coordinates & bounding box"""
    headers = {
        "User-Agent": "PESLeadsExtractor/1.0 (contact: pesleadsextractor@gmail.com)",
        "Accept-Language": "en"
    }
    params = {"q": city, "format": "json", "limit": 1}
    r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data:
        st.error("City not found.")
        return None
    item = data[0]
    bbox = list(map(float, item["boundingbox"]))  # [S, N, W, E]
    lat, lon = float(item["lat"]), float(item["lon"])
    return lat, lon, bbox


def expand_bbox(bbox, padding_km):
    s, n, w, e = bbox
    pad_lat = padding_km / 111.0
    mid = (s + n) / 2
    pad_lon = padding_km / (111.0 * math.cos(math.radians(mid)))
    return [s - pad_lat, n + pad_lat, w - pad_lon, e + pad_lon]


def extract_data(city, radius_km=8):
    """Fetch business data for the city"""
    geo = geocode(city)
    if not geo:
        return pd.DataFrame()
    lat, lon, bbox = geo
    bbox = expand_bbox(bbox, radius_km)
    query = f"""
    [out:json][timeout:60];
    (
      node["office"="company"]({bbox[0]},{bbox[2]},{bbox[1]},{bbox[3]});
      node["shop"]({bbox[0]},{bbox[2]},{bbox[1]},{bbox[3]});
      node["amenity"="company"]({bbox[0]},{bbox[2]},{bbox[1]},{bbox[3]});
    );
    out center;
    """
    headers = {"User-Agent": "PESLeadsExtractor/1.0 (contact: pesleadsextractor@gmail.com)"}
    r = requests.post(OVERPASS_URL, data={"data": query}, headers=headers, timeout=90)
    r.raise_for_status()
    elements = r.json().get("elements", [])

    rows = []
    for e in elements:
        t = e.get("tags", {})
        phone = t.get("phone") or t.get("contact:phone")
        if not phone:  # ✅ skip if no phone number
            continue
        rows.append({
            "Company Name": t.get("name") or t.get("brand") or t.get("office") or t.get("shop"),
            "Phone": phone,
            "Email": t.get("email") or t.get("contact:email"),
            "Address": ", ".join(filter(None, [
                t.get("addr:housenumber"),
                t.get("addr:street"),
                t.get("addr:city"),
                t.get("addr:postcode")
            ])),
            "Latitude": e.get("lat") or e.get("center", {}).get("lat"),
            "Longitude": e.get("lon") or e.get("center", {}).get("lon"),
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["Company Name","Phone"])
    return df


def to_excel(df):
    """Convert DataFrame to Excel bytes for download"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
    return output.getvalue()


# ---- Streamlit UI ----
st.set_page_config(page_title="PES Cold data extractor AI Agent", layout="wide")
st.title("📍Pvt Company Data Leads Extractor AI Agent by PES")
st.caption("Free business data fetcher using OpenStreetMap – made by PES")

# ---- Dropdown of Pune regions ----
zones = ["Pune", "PCMC", "Baner", "Kothrud", "Wakad", "Hinjewadi", "Hadapsar", "Viman Nagar", "Kharadi"]
city = st.selectbox("Select Pune region:", zones)
radius = st.slider("Search Radius (km):", 2, 20, 8)

if st.button("🔎 Find Data"):
    with st.spinner(f"Fetching business data for {city}..."):
        try:
            df = extract_data(city, radius_km=radius)
            if len(df) == 0:
                st.warning("No business data with phone numbers found in this region.")
            else:
                st.success(f"✅ Found {len(df)} companies with phone numbers in {city}")
                st.dataframe(df.head(20))
                excel_bytes = to_excel(df)
                st.download_button(
                    label="⬇️ Download Excel File",
                    data=excel_bytes,
                    file_name=f"{city.replace(' ','_')}_pvt_leads.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Error: {e}")

import streamlit as st
import base64
import re
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import os
import subprocess

# install playwright browser only if not already installed
if not os.path.exists("/home/appuser/.cache/ms-playwright"):
    subprocess.run(["playwright", "install", "chromium"])

from playwright.sync_api import sync_playwright

URL = "https://www.chmi.cz/namerena-data/webkamery"

WIDTH = 200
HEIGHT = 150

# ----------------------
# CACHE (10 minutes)
# ----------------------
@st.cache_data(ttl=600)
def scrape_images():
    image_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)

        # wait for first images
        page.wait_for_selector("img")

        count = 0

        for page_number in range(1, 10):
            if page_number > 1:
                try:
                    btn = page.locator(f"//button[text()='{page_number}']")
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    page.wait_for_timeout(3000)
                except:
                    continue

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            imgs = soup.find_all("img")

            for img in imgs:
                src = img.get("src", "")
                alt = img.get("alt", f"image_{count}")

                clean_alt = re.sub(r'^Náhled webkamery\s+', '', alt)

                if src.startswith("data:image"):
                    try:
                        header, data = src.split(",", 1)
                        image_bytes = base64.b64decode(data)

                        image = Image.open(BytesIO(image_bytes))

                        # resize
                        image = image.resize((WIDTH, HEIGHT))

                        if clean_alt and len(clean_alt) > 3:
                            image_data.append({
                                "img": image,
                                "alt": clean_alt
                            })

                        count += 1

                    except:
                        pass

        browser.close()

    return image_data


# ----------------------
# SIMPLE MATCHING (optional)
# ----------------------
def match_webcams(image_data):
    final = []

    for item in image_data:
        final.append({
            "name": item["alt"],
            "img": item["img"],
            "link": "http://kamery.chmi.cz"  # fallback
        })

    return final


# ----------------------
# UI
# ----------------------
st.set_page_config(layout="wide")
st.title("📷 Webkamery ČHMÚ")

if st.button("🔄 Refresh now"):
    st.cache_data.clear()

with st.spinner("Scraping webcams (this may take ~20s)..."):
    data = scrape_images()

final_data = match_webcams(data)

# grid
cols = st.columns(5)

for i, cam in enumerate(final_data):
    with cols[i % 5]:
        st.markdown(
            f"""
            <a href="{cam['link']}" target="_blank">
            """,
            unsafe_allow_html=True
        )

        st.image(cam["img"], use_container_width=True)

        st.markdown("</a>", unsafe_allow_html=True)
        st.caption(cam["name"])

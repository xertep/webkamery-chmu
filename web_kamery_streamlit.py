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
# CACHE
# ----------------------
@st.cache_data(ttl=600)
def scrape_images():
    image_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)
        page.wait_for_selector("img")

        count = 0

        for page_number in range(1, 10):
            if page_number > 1:
                try:
                    btn = page.locator(f"//button[contains(@class,'chmi-pagination__btn') and text()='{page_number}']")
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    page.wait_for_timeout(3000)
                except:
                    continue

            soup = BeautifulSoup(page.content(), "html.parser")

            for img in soup.find_all("img"):
                src = img.get("src", "")
                alt = img.get("alt", "")

                # 🔑 FILTER → only real webcam thumbnails
                if not alt.startswith("Náhled webkamery"):
                    continue

                clean_alt = re.sub(r'^Náhled webkamery\s+', '', alt)

                if src.startswith("data:image"):
                    try:
                        header, data = src.split(",", 1)
                        image_bytes = base64.b64decode(data)

                        # detect gif vs jpg from header
                        is_gif = "gif" in header.lower()

                        if is_gif:
                            # keep raw bytes → preserves animation
                            image_data.append({
                                "img_bytes": image_bytes,
                                "alt": clean_alt,
                                "is_gif": True
                            })
                        else:
                            # resize only static images
                            from PIL import Image
                            image = Image.open(BytesIO(image_bytes))
                            image = image.convert("RGB").resize((WIDTH, HEIGHT))

                            buffer = BytesIO()
                            image.save(buffer, format="JPEG")

                            image_data.append({
                                "img_bytes": buffer.getvalue(),
                                "alt": clean_alt,
                                "is_gif": False
                            })

                        count += 1

                    except:
                        pass

        browser.close()

    return image_data


# ----------------------
# MATCH WITH LINKS (simplified but correct)
# ----------------------
def match_webcams(image_data, webcam_links):
    final = {}

    for name, link in webcam_links.items():
        place_name = name.split(" -")[0]
        matched = None

        for item in image_data:
            img_place = item["alt"].split(" (")[0]

            if place_name == img_place:
                matched = item
                break

        final[name] = {
            "img": matched["img_bytes"] if matched else None,
            "link": link
        }

    return final


# ----------------------
# YOUR webcam_links (keep as-is)
# ----------------------
webcam_links = {
    "Cheb - 483 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=11406",
    "Dyleň - 940 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=L2DYLE01",
    # 👉 KEEP YOUR FULL DICT HERE (unchanged)
}


# ----------------------
# UI
# ----------------------
st.set_page_config(layout="wide")
st.title("📷 Webkamery ČHMÚ")

st.markdown("""
<style>
img {
    border-radius: 8px;
}

[data-testid="stVerticalBlock"] > div {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

if st.button("🔄 Refresh now"):
    st.cache_data.clear()

with st.spinner("Scraping webcams..."):
    image_data = scrape_images()

final = match_webcams(image_data, webcam_links)

cols_per_row = 5
items = list(final.items())

for i in range(0, len(items), cols_per_row):
    row_items = items[i:i + cols_per_row]
    cols = st.columns(cols_per_row)

    for col, (name, data) in zip(cols, row_items):
        with col:
            if data["img"]:
                st.markdown(f'<a href="{data["link"]}" target="_blank">', unsafe_allow_html=True)
                st.image(data["img"], width=200)
                st.markdown('</a>', unsafe_allow_html=True)
            else:
                st.write("⬜")

            st.caption(name)

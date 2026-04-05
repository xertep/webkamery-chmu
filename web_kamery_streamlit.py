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


def create_placeholder():
    img = Image.new("RGB", (WIDTH, HEIGHT), (220, 220, 220))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()

PLACEHOLDER_IMG = create_placeholder()

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

                # 🔑 extract place + direction
                match = re.match(r"(.+?)\s*\((.+?)\)", clean_alt)

                if match:
                    place = match.group(1).strip()
                    direction = match.group(2).strip()

                    key = f"{place} ({direction})"
                else:
                    key = clean_alt.strip()

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
                                "key": key,
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
                                "key": key,
                                "is_gif": False
                            })

                        count += 1

                    except:
                        pass

        browser.close()

    return image_data


def normalize_name(name):
    parts = name.split(" -")
    place = parts[0]

    # extract direction (before "směr")
    direction = parts[-1].replace("směr", "").strip()

    return f"{place} ({direction})"


# ----------------------
# MATCH WITH LINKS (simplified but correct)
# ----------------------
def match_webcams(image_data, webcam_links):
    final = {}

    # 🔑 build lookup dictionary (fast + no duplicates)
    image_lookup = {item["key"]: item for item in image_data}

    for name, link in webcam_links.items():
        key = normalize_name(name)

        matched = image_lookup.get(key)

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
    "Šindelová - 587 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=L3SIND01",
    "Přimda - 750 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=11423",
    "Karlovy Vary - 620 m n.m. - VJV směr": "http://kamery.chmi.cz/webcam.php?cam=11414",
    "Karlovy Vary - 620 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11414_2",
    "Krásné Údolí - 644 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=L2KRAU01",
    "Klínovec - 1235 m n.m. - ZJZ směr": "http://kamery.chmi.cz/webcam.php?cam=L3KLIN01",
    "Kdyně-Koráb - 773 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=kdyne",
    "Měděnec - 828 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=U1MEDE01",
    "Hojsova Stráž - 867 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=L1HOJS01",
    "Klatovy - 425 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=L1KLAT01",
    "Tušimice - 322 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11438",
    "Plzeň-Mikulka - 360 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11450_2",
    "Plzeň-Mikulka - otočná kamera": "http://kamery.chmi.cz/webcam.php?cam=11450",
    "Plzeň-Mikulka - 360 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11450_3",
    "Strojetice - 371 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=U1STRJ01",
    "Svatobor - 900 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=svatobor",
    "Kralovice - 448 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=L2KRAL01",
    "Horská Kvilda - 1072 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=C1HKVI01",
    "Kašperk - 914 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=kasperk",
    "Vlkonice - 493 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=C1VLKO01",
    "Bučina - 1172 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=bucina",
    "Churáňov - 1118 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=11457",
    "Kopisty - 240 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=11433",
    "Radar Brdy - 912 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=brdy",
    "Kocelovice - 525 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11487",
    "Teplice - 252 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=U1TEPL01",
    "Smolnice - 345 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=U1SMOL01",
    "Rožmitál p. Třem. - 538 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=C1ROZM01",
    "Volary - 745 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=volary",
    "Milešovka - 836 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11464",
    "Libín Prachatice - 1096 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=libinprach",
    "Ústí nad Labem - 377 m n.m. - JJZ směr": "http://kamery.chmi.cz/webcam.php?cam=11502",
    "Příbram - 551 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=P1PRIB01",
    "Doksany - 158 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11509",
    "Frymburk - 815 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=frymburk",
    "Temelín - 505 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11538",
    "Praha-Libuš - 340 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11520_2",
    "Praha-Libuš - 340 m n.m. - VSV směr": "http://kamery.chmi.cz/webcam.php?cam=11520",
    "Nadějkov - 610 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=C2NADV01",
    "České Budějovice - 388 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=11546",
    "Varnsdorf - 365 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=U2VARN01",
    "Nové Hrady - 546 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=nove_hrady",
    "Ondřejov - 485 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=P3ONDR01",
    "Mrzky - 260 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=P2MRZK01",
    "Vlašim - 415 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=P3VLAS01",
    "Liberec - 397 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11603",
    "Frýdlant - 339 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=U2FRYD01",
    "Poděbrady - 189 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=H3PODE01",
    "Turnov - 252 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=P2TURN01",
    "Hejnice - 396 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=U2HEJN01",
    "Jizerka - 858 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=P2KORE01",
    "Jičín - 283 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=H3JICI01",
    "Kostelní Myslová - 569 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11636",
    "Labská bouda - 1320 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=H1LBOU01",
    "Luční bouda - 1413 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=H1LUCB01",
    "Sněžka - 1603 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=H1SNEZ01",
    "Seč - 520 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=H3SECA01",
    "Přibyslav - 530 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11659",
    "Hradec Králové - 278 m n.m. - ZJZ směr": "http://kamery.chmi.cz/webcam.php?cam=H3HRAD01",
    "Svratouch - 737 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11683",
    "Kuchařovice - 334 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11698",
    "Dukovany - 400 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11693",
    "Dyjákovice - 201 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=B2DYJA01",
    "Nedvězí - 722 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=B2NEDV01",
    "Polom - 748 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=11669",
    "Broumov - 373 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=H3BROU01",
    "Ústí nad Orlicí - 402 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11679",
    "Brno - 240 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=B2BZAB01",
    "Radar Skalky - 767 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=skalky",
    "Kobylí - 172 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=B2KOBY01",
    "Slaměnka - 1100 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=O2SLAM01",
    "Luká - 510 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11710",
    "Paprsek - 1020 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=O2PAPR01",
    "Ivanovice na Hane - 240 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=B1IVAN01",
    "Šerák - 1328 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=11730",
    "Osoblaha - 238 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=O1OSOB01",
    "Olomouc - 210 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=O2OLOM01",
    "Rýmařov - 603 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=O1RYMA01",
    "Holešov - 224 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=11774",
    "Vítkov - 490 m n.m. - JJZ směr": "http://kamery.chmi.cz/webcam.php?cam=O1VITK01",
    "Bělotín - 298 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=O1BELO01",
    "Maruška - 664 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=O3MARU02",
    "Maruška - 664 m n.m.": "http://kamery.chmi.cz/webcam.php?cam=O3MARU01",
    "Štítná nad Vláří - 325 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=B1STIT01",
    "Vsetín - 387 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=O3VSET01",
    "Ostrava-Poruba - 252 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=O1PORU01",
    "Ostrava-Mošnov - 277 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=11782",
    "Ostrava-Mošnov - 277 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11782_2",
    "Lysá hora - 1324 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=11787_1",
    "Lysá hora - 1324 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11787_2",
    "Javorový vrch - 940 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=O1JAVR01",
    "Lysá hora - 1324 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11787_3"
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
    text-align: left;
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
                st.image(data["img"], width=200)
            else:
                st.image(PLACEHOLDER_IMG, width=200)

            st.link_button("🔗 Open webcam", data["link"])

            st.caption(name)

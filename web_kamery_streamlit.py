import streamlit as st
import base64
import re
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import os
import subprocess
import time
from streamlit_autorefresh import st_autorefresh

# install playwright browser only if not already installed
# if not os.path.exists("/home/appuser/.cache/ms-playwright"):
#    subprocess.run(["playwright", "install", "chromium"])

from playwright.sync_api import sync_playwright

if "cached_data" not in st.session_state:
    st.session_state.cached_data = None

if "last_update_time" not in st.session_state:
    st.session_state.last_update_time = time.time()

st.set_page_config(
    page_title = "ČHMÚ webkamery",
    page_icon="📷",
    layout="wide"
    )

st_autorefresh(interval=600000, key="refresh")

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()


URL = "https://www.chmi.cz/namerena-data/webkamery"

WIDTH = 200
HEIGHT = 150


def create_placeholder():
    img = Image.new("RGB", (WIDTH, HEIGHT), (220, 220, 220))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()

PLACEHOLDER_IMG = create_placeholder()

if "cached_data" not in st.session_state:
    st.session_state.cached_data = None

# ----------------------
# CACHE
# ----------------------
@st.cache_data(ttl=600)
def scrape_images():
    image_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, timeout=60000, wait_until="networkidle")
        page.wait_for_timeout(2000)

        for page_number in range(1, 10):

            if page_number > 1:
                try:
                    btn = page.locator(
                        f"//button[contains(@class,'chmi-pagination__btn') and text()='{page_number}']"
                    )

                    btn.scroll_into_view_if_needed()
                    btn.click()

                    # 🔑 IMPORTANT: wait for full re-render
                    page.wait_for_load_state("networkidle")
                    page.wait_for_selector("img[alt^='Náhled webkamery']", timeout=5000)

                except:
                    continue

            soup = BeautifulSoup(page.content(), "html.parser")

            for a in soup.find_all("a", href=True):

                img = a.find("img")
                if not img:
                    continue

                href = a["href"]  # 🔑 THIS IS THE PUBLIC LINK

                src = img.get("src") or img.get("data-src") or ""
                alt = img.get("alt", "")

                # 🔑 make absolute URL if needed
                if href.startswith("/"):
                    href = "https://www.chmi.cz" + href

                if not alt.startswith("Náhled webkamery"):
                    continue

                clean_alt = re.sub(r'^Náhled webkamery\s+', '', alt)

                match = re.match(r"(.+?)\s*\((.+?)\)", clean_alt)

                if match:
                    place = match.group(1).strip()
                    direction = match.group(2).strip()
                    key = f"{place} ({direction})"
                else:
                    key = clean_alt.strip()

                # -------------------------
                # CASE 1: base64 image
                # -------------------------
                if src.startswith("data:image"):
                    try:
                        header, data = src.split(",", 1)
                        image_bytes = base64.b64decode(data)

                        is_gif = "gif" in header.lower()

                        if is_gif:
                            image_data.append({
                                "img_bytes": image_bytes,
                                "key": key,
                                "link": href,
                                "is_gif": True
                            })
                        else:
                            image = Image.open(BytesIO(image_bytes))
                            image = image.convert("RGB").resize((WIDTH, HEIGHT))

                            buffer = BytesIO()
                            image.save(buffer, format="JPEG")

                            image_data.append({
                                "img_bytes": buffer.getvalue(),
                                "key": key,
                                "link": href,
                                "is_gif": False
                            })

                    except:
                        pass

                # -------------------------
                # CASE 2: real image URL (NEW FIX)
                # -------------------------
                elif src.startswith("http"):
                    try:
                        import requests

                        r = requests.get(src, timeout=10)
                        image_bytes = r.content

                        image = Image.open(BytesIO(image_bytes))
                        image = image.convert("RGB").resize((WIDTH, HEIGHT))

                        buffer = BytesIO()
                        image.save(buffer, format="JPEG")

                        image_data.append({
                            "img_bytes": buffer.getvalue(),
                            "key": key,
                            "link": href,
                            "is_gif": False
                        })

                    except:
                        pass

        browser.close()

    return image_data


# ----------------------
# MATCH WITH LINKS (simplified but correct)
# ----------------------
def match_webcams(image_data, webcam_links):
    final = {}

    # scraped lookup: already in format "Place (Direction)"
    image_lookup = {item["key"]: item for item in image_data}

    for full_name, link in webcam_links.items():

        # 🔑 NEW: base name is EXACTLY what's before " /"
        base_name = full_name.split(" /")[0].strip()

        matched = image_lookup.get(base_name)

        final[full_name] = {
            "img": matched["img_bytes"] if matched else None,
            "link": matched.get("link", link) if matched else link
        }

    return final


# ----------------------
# YOUR webcam_links (keep as-is)
# ----------------------
webcam_links = {
    "Cheb (SV) / Cheb - 483 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=11406",
    "Dyleň (Z-SZ) / Dyleň - 940 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=L2DYLE01",
    "Šindelová (Z) / Šindelová - 587 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=L3SIND01",
    "Přimda (V) / Přimda - 750 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=11423",
    "Karlovy Vary (V-JV) / Karlovy Vary - 620 m n.m. - VJV směr": "http://kamery.chmi.cz/webcam.php?cam=11414",
    "Karlovy Vary (JZ) / Karlovy Vary - 620 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11414_2",
    "Karlovy Vary (JV) / Karlovy Vary - 620 m n.m. - VJV směr": "https://www.chmi.cz/namerena-data/webkamera/lkkv3-karlovy-vary",
    "Krásné Údolí (SV) / Krásné Údolí - 644 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=L2KRAU01",
    "Klínovec (Z-JZ) / Klínovec - 1235 m n.m. - ZJZ směr": "http://kamery.chmi.cz/webcam.php?cam=L3KLIN01",
    "Kdyně-Koráb (Z) / Kdyně-Koráb - 773 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=kdyne",
    "Měděnec (V) / Měděnec - 828 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=U1MEDE01",
    "Hojsova Stráž (S) / Hojsova Stráž - 867 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=L1HOJS01",
    "Klatovy (J) / Klatovy - 425 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=L1KLAT01",
    "Tušimice (S) / Tušimice - 322 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11438",
    "Plzeň-Mikulka (JZ) / Plzeň-Mikulka - 360 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11450_2",
    "Plzeň-Mikulka (otočný) / Plzeň-Mikulka - otočná kamera": "http://kamery.chmi.cz/webcam.php?cam=11450",
    "Plzeň-Mikulka (S) / Plzeň-Mikulka - 360 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11450_3",
    "Strojetice (JZ) / Strojetice - 371 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=U1STRJ01",
    "Svatobor (V) / Svatobor - 900 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=svatobor",
    "Kralovice (Z) / Kralovice - 448 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=L2KRAL01",
    "Horská Kvilda (JV) / Horská Kvilda - 1072 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=C1HKVI01",
    "Kašperk (Z) / Kašperk - 914 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=kasperk",
    "Vlkonice (SZ) / Vlkonice - 493 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=C1VLKO01",
    "Bučina (J-JV) / Bučina - 1172 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=bucina",
    "Churáňov (SV) / Churáňov - 1118 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=11457",
    "Kopisty (V) / Kopisty - 240 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=11433",
    "Radar Brdy (JV) / Radar Brdy - 912 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=brdy",
    "Kocelovice (S-SZ) / Kocelovice - 525 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11487",
    "Teplice (Z) / Teplice - 252 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=U1TEPL01",
    "Teplice (JV) / Teplice - 252 m n.m. - JV směr": "https://www.chmi.cz/namerena-data/webkamera/teplice2-teplice",
    "Smolnice (S) / Smolnice - 345 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=U1SMOL01",
    "Rožmitál p. Třem. (J) / Rožmitál p. Třem. - 538 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=C1ROZM01",
    "Volary (S) / Volary - 745 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=volary",
    "Milešovka (J) / Milešovka - 836 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11464",
    "Libín Prachatice (SZ) / Libín Prachatice - 1096 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=libinprach",
    "Ústí nad Labem (J-JZ) / Ústí nad Labem - 377 m n.m. - JJZ směr": "http://kamery.chmi.cz/webcam.php?cam=11502",
    "Příbram (JZ) / Příbram - 551 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=P1PRIB01",
    "Doksany (JZ) / Doksany - 158 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11509",
    "Frymburk - 815 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=frymburk",
    "Temelín (JV) / Temelín - 505 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11538",
    "Praha-Libuš (S) / Praha-Libuš - 340 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11520_2",
    "Praha-Libuš (VSV) / Praha-Libuš - 340 m n.m. - VSV směr": "http://kamery.chmi.cz/webcam.php?cam=11520",
    "Nadějkov (JV) / Nadějkov - 610 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=C2NADV01",
    "České Budějovice (Z) / České Budějovice - 388 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=11546",
    "Varnsdorf (JV) / Varnsdorf - 365 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=U2VARN01",
    "Nové Hrady (JZ) / Nové Hrady - 546 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=nove_hrady",
    "Ondřejov (JV) / Ondřejov - 485 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=P3ONDR01",
    "Mrzky (J) / Mrzky - 260 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=P2MRZK01",
    "Vlašim (Z) / Vlašim - 415 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=P3VLAS01",
    "Liberec (JZ) / Liberec - 397 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11603",
    "Košetice (S) / Košetice - 534 m n.m. - S směr": "https://www.chmi.cz/namerena-data/webkamera/kosetice-kosetice",
    "Frýdlant (JZ) / Frýdlant - 339 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=U2FRYD01",
    "Poděbrady (SZ) / Poděbrady - 189 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=H3PODE01",
    "Turnov (S) / Turnov - 252 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=P2TURN01",
    "Hejnice (J) / Hejnice - 396 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=U2HEJN01",
    "Jizerka (V) / Jizerka - 858 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=P2KORE01",
    "Jičín (JZ) / Jičín - 283 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=H3JICI01",
    "Kostelní Myslová (J) / Kostelní Myslová - 569 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11636",
    "Labská bouda (J) / Labská bouda - 1320 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=H1LBOU01",
    "Luční bouda (V) / Luční bouda - 1413 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=H1LUCB01",
    "Pec pod Sněžkou (S) / Pec pod Sněžkou - 1046 m n.m. - S směr": "https://www.chmi.cz/namerena-data/webkamera/pecpodsnezkou-pec-pod-snezkou",
    "Sněžka (Z) / Sněžka - 1603 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=H1SNEZ01",
    "Seč (J) / Seč - 520 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=H3SECA01",
    "Přibyslav (JZ) / Přibyslav - 530 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11659",
    "Hradec Králové (Z-JZ) / Hradec Králové - 278 m n.m. - ZJZ směr": "http://kamery.chmi.cz/webcam.php?cam=H3HRAD01",
    "Svratouch (J) / Svratouch - 737 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11683",
    "Kuchařovice (J) / Kuchařovice - 334 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=11698",
    "Dukovany (JV) / Dukovany - 400 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11693",
    "Dyjákovice (S) / Dyjákovice - 201 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=B2DYJA01",
    "Nedvězí (J) / Nedvězí - 722 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=B2NEDV01",
    "Polom (Z) / Polom - 748 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=11669",
    "Broumov (SV) / Broumov - 373 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=H3BROU01",
    "Ústí nad Orlicí (Z-JZ) / Ústí nad Orlicí - 402 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11679",
    "Brno (SV) / Brno - 240 m n.m. - SV směr": "http://kamery.chmi.cz/webcam.php?cam=B2BZAB01",
    "Radar Skalky (SZ) / Radar Skalky - 767 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=skalky",
    "Kobylí (S) / Kobylí - 172 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=B2KOBY01",
    "Slaměnka (J) / Slaměnka - 1100 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=O2SLAM01",
    "Luká (S) / Luká - 510 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=11710",
    "Paprsek (J) / Paprsek - 1020 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=O2PAPR01",
    "Ivanovice na Hane (J) / Ivanovice na Hane - 240 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=B1IVAN01",
    "Šerák (V) / Šerák - 1328 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=11730",
    "Osoblaha (JZ) / Osoblaha - 238 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=O1OSOB01",
    "Olomouc (J) / Olomouc - 210 m n.m. - J směr": "http://kamery.chmi.cz/webcam.php?cam=O2OLOM01",
    "Rýmařov (SZ) / Rýmařov - 603 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=O1RYMA01",
    "Holešov (Z) / Holešov - 224 m n.m. - Z směr": "http://kamery.chmi.cz/webcam.php?cam=11774",
    "Vítkov (J-JZ) / Vítkov - 490 m n.m. - JJZ směr": "http://kamery.chmi.cz/webcam.php?cam=O1VITK01",
    "Bělotín (V) / Bělotín - 298 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=O1BELO01",
    "Maruška (V) / Maruška - 664 m n.m. - V směr": "http://kamery.chmi.cz/webcam.php?cam=O3MARU02",
    "Maruška / Maruška - 664 m n.m.": "http://kamery.chmi.cz/webcam.php?cam=O3MARU01",
    "Štítná nad Vláří (JV) / Štítná nad Vláří - 325 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=B1STIT01",
    "Valašské Meziříčí (SV) / Valašské Meziříčí - 335 m n.m. - JV směr": "https://www.chmi.cz/namerena-data/webkamera/valmez-valasske-mezirici",
    "Vsetín (JV) / Vsetín - 387 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=O3VSET01",
    "Ostrava-Poruba (JV) / Ostrava-Poruba - 252 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=O1PORU01",
    "Ostrava-Mošnov (S) / Ostrava-Mošnov - 277 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=11782",
    "Ostrava-Mošnov (JJV) / Ostrava-Mošnov - 277 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11782_2",
    "Horní Bečva (SSZ) / Horní Bečva - 618 m n.m. - SSZ směr": "https://www.chmi.cz/namerena-data/webkamera/hornibecva-horni-becva",
    "Lysá hora (SZ) / Lysá hora - 1324 m n.m. - SZ směr": "http://kamery.chmi.cz/webcam.php?cam=11787_1",
    "Lysá hora (JV) / Lysá hora - 1324 m n.m. - JV směr": "http://kamery.chmi.cz/webcam.php?cam=11787_2",
    "Javorový vrch (S) / Javorový vrch - 940 m n.m. - S směr": "http://kamery.chmi.cz/webcam.php?cam=O1JAVR01",
    "Lysá hora (JZ) / Lysá hora - 1324 m n.m. - JZ směr": "http://kamery.chmi.cz/webcam.php?cam=11787_3"
}


def short_name(full_name):
    if " / " in full_name:
        return full_name.split(" / ", 1)[1].strip()
    return full_name



# ----------------------
# UI
# ----------------------
st.set_page_config(layout="wide")
st.title("📷 Webkamery ČHMÚ")

if st.session_state.get("last_update_time") is not None:
    age = time.time() - st.session_state.last_update_time

    if age < 120:
        status = "🟢 živě"
    elif age < 240:
        status = "🟡 nedávno"
    else:
        status = "⚪ starší"

    st.caption(
        f"{status} • Aktualizováno {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_update_time))} UTC"
    )

st.markdown("""
<style>
/* remove gap under image */
img {
    border-radius: 8px;
    margin-bottom: 2px;
}

/* tighten button spacing */
div[data-testid="stLinkButton"] {
    margin-top: -8px;
}

/* add spacing between rows */
.row-spacing {
    margin-bottom: 25px;
}
</style>
""", unsafe_allow_html=True)

if st.button("🔄 Obnovit stránku"): 
    st.cache_data.clear()


# ----------------------
# LOAD DATA (silent refresh style)
# ----------------------
if st.session_state.cached_data is None:
    # FIRST LOAD → show spinner
    with st.spinner("Načítám webkamery..."):
        image_data = scrape_images()
        final = match_webcams(image_data, webcam_links)

        st.session_state.cached_data = final
        st.session_state.last_update_time = time.time()

else:
    # show cached immediately
    final = st.session_state.cached_data

    try:
        image_data = scrape_images()
        new_final = match_webcams(image_data, webcam_links)

        st.session_state.cached_data = new_final
        st.session_state.last_update_time = time.time()  # ALWAYS update

    except:
        pass



cols_per_row = 4
items = list(final.items())

for i in range(0, len(items), cols_per_row):
    row_items = items[i:i + cols_per_row]

    # 👇 row wrapper (this creates spacing BETWEEN rows)
    st.markdown('<div class="row-spacing">', unsafe_allow_html=True)

    cols = st.columns(cols_per_row)

    for col, (name, data) in zip(cols, row_items):
        with col:

            if data["img"]:
                st.image(data["img"], width=200)
            else:
                st.image(PLACEHOLDER_IMG, width=200)

            st.link_button(
                short_name(name),
                data["link"]
            )

    st.markdown('</div>', unsafe_allow_html=True)

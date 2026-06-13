# pip install selenium webdriver-manager requests beautifulsoup4

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSf3IKsba9-2qnj5Byn-NCgHB6EXQzDEdXfA0OtwYEkWDbuPsQ/viewform?hr_submission=ChkIi8-4588BEhAIwJPbv_YYEgcIo-WxwPYYEAE"
OUT_DIR = "galaxy_images"

os.makedirs(OUT_DIR, exist_ok=True)

def clean_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    return name.strip()

options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,3000")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

driver.get(FORM_URL)
time.sleep(5)

# прокрутка сторінки, щоб підвантажились всі фото
last_height = 0
while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        break
    last_height = new_height

html = driver.page_source
driver.quit()

soup = BeautifulSoup(html, "html.parser")

items = []

# Google Forms зазвичай має блоки питань із role="listitem"
for block in soup.select('[role="listitem"]'):
    text = block.get_text("\n", strip=True)

    # шукаємо назву галактики
    match = re.search(r'\b(NGC\s*\d+|IC\s*\d+|M\s*\d+)\b', text, re.IGNORECASE)
    if not match:
        continue

    name = clean_filename(match.group(1).upper().replace(" ", "_"))

    img = block.find("img")
    if not img:
        continue

    img_url = img.get("src")
    if not img_url:
        continue

    items.append((name, img_url))

print(f"Знайдено фото: {len(items)}")

for i, (name, url) in enumerate(items, start=1):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()

        ext = ".jpg"
        content_type = r.headers.get("content-type", "")
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"

        filename = f"{i:02d}_{name}{ext}"
        path = os.path.join(OUT_DIR, filename)

        with open(path, "wb") as f:
            f.write(r.content)

        print("Збережено:", filename)

    except Exception as e:
        print("Помилка:", name, e)
"""
PartSelect repair guide scraper.

Navigates live PartSelect repair pages using Chrome (JS required for
symptom lists — httpx alone cannot see this content).

Covers /Repair/Refrigerator/ and /Repair/Dishwasher/.

Each repair guide captures:
  symptom name, description, frequency %, parts list (with PS numbers),
  repair difficulty, video URL, step tips, and the detail page URL.

Output: data/repairs_raw.json

Run: python scrape_repairs.py
Requires: pip install selenium  (ChromeDriver must match your Chrome version)
"""
import json
import random
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ── Config ────────────────────────────────────────────────────────────────────

TARGETS = {
    "refrigerator": "https://www.partselect.com/Repair/Refrigerator/",
    "dishwasher":   "https://www.partselect.com/Repair/Dishwasher/",
}
PAGE_WAIT  = 20   # seconds to wait for elements
OUT_PATH   = Path("data/repairs_raw.json")


# ── Driver setup ──────────────────────────────────────────────────────────────

def _build_driver(headless: bool = True) -> webdriver.Chrome:
    """Create a Chrome driver configured to avoid bot-detection fingerprints."""
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    # Remove navigator.webdriver flag so PartSelect's JS fingerprinting doesn't flag us
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)
    return driver


# ── Navigation ────────────────────────────────────────────────────────────────

def _go(driver: webdriver.Chrome, url: str, retries: int = 3) -> bool:
    """Navigate to url, waiting for full page load. Returns False if all retries fail."""
    for attempt in range(retries):
        try:
            if attempt:
                time.sleep(random.uniform(3, 7))
            driver.get(url)
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            if "Access Denied" in driver.title or "403" in driver.title:
                print(f"    Access denied (attempt {attempt + 1})")
                continue
            return True
        except Exception as exc:
            print(f"    Navigation error attempt {attempt + 1}: {exc}")
    return False


def _text(el) -> str:
    try:
        return el.text.strip()
    except Exception:
        return ""


# ── Symptom listing page ──────────────────────────────────────────────────────

def _collect_symptom_cards(driver: webdriver.Chrome, listing_url: str) -> list[dict]:
    """
    Load the repair listing page and snapshot all symptom cards.
    We grab all data from each anchor immediately — before navigation changes the DOM.
    """
    if not _go(driver, listing_url):
        return []

    try:
        WebDriverWait(driver, PAGE_WAIT).until(
            EC.presence_of_element_located((By.CLASS_NAME, "symptom-list"))
        )
    except TimeoutException:
        print("  Symptom list did not appear — check if page needs login")
        return []

    cards: list[dict] = []
    anchors = driver.find_elements(By.CSS_SELECTOR, ".symptom-list a")

    for anchor in anchors:
        try:
            href = anchor.get_attribute("href") or ""
            if not href:
                continue

            try:
                name = _text(anchor.find_element(By.CLASS_NAME, "title-md"))
            except NoSuchElementException:
                continue
            if not name:
                continue

            try:
                description = _text(anchor.find_element(By.TAG_NAME, "p"))
            except NoSuchElementException:
                description = ""

            frequency = ""
            try:
                pct_el = anchor.find_element(By.CLASS_NAME, "symptom-list__reported-by")
                m = re.search(r"(\d+)", _text(pct_el))
                frequency = m.group(1) + "%" if m else ""
            except NoSuchElementException:
                pass

            cards.append({
                "name":        name,
                "description": description,
                "frequency":   frequency,
                "url":         href,
            })

        except StaleElementReferenceException:
            continue
        except Exception as exc:
            print(f"  Card parse error: {exc}")

    return cards


# ── Symptom detail page ───────────────────────────────────────────────────────

def _scrape_detail(driver: webdriver.Chrome, url: str) -> dict:
    """
    Visit a single symptom detail page and extract:
      parts (with PS numbers), difficulty rating, YouTube video URL, repair tips.
    """
    detail: dict = {"parts": [], "difficulty": "", "video_url": "", "tips": []}

    if not _go(driver, url):
        return detail

    try:
        WebDriverWait(driver, PAGE_WAIT).until(
            EC.presence_of_element_located((By.CLASS_NAME, "repair__intro"))
        )
    except TimeoutException:
        return detail

    # Parts that fix this symptom (anchor text + nearby PS numbers)
    try:
        part_anchors = driver.find_elements(
            By.CSS_SELECTOR, "div.repair__intro a.js-scrollTrigger"
        )
        for a in part_anchors:
            name = _text(a)
            href = a.get_attribute("href") or ""
            ps_m = re.search(r"PS(\d+)", href + name)
            entry = name if not ps_m else f"{name} (PS{ps_m.group(1)})"
            if entry:
                detail["parts"].append(entry)
    except Exception:
        pass

    # Difficulty rating
    try:
        items = driver.find_elements(By.CSS_SELECTOR, "ul.list-disc li")
        for item in items:
            txt = _text(item)
            if "Rated as" in txt or "difficulty" in txt.lower():
                detail["difficulty"] = txt.replace("Rated as", "").strip()
                break
    except Exception:
        pass

    # YouTube video
    try:
        yt_el = driver.find_element(By.CSS_SELECTOR, "div[data-yt-init]")
        vid_id = yt_el.get_attribute("data-yt-init") or ""
        if vid_id:
            detail["video_url"] = f"https://www.youtube.com/watch?v={vid_id}"
    except NoSuchElementException:
        pass

    # Step-by-step tips
    try:
        step_items = driver.find_elements(
            By.CSS_SELECTOR, ".repair-story__intro li, .repair__steps li"
        )
        detail["tips"] = [_text(li) for li in step_items[:8] if _text(li)]
    except Exception:
        pass

    return detail


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    Path("data").mkdir(exist_ok=True)
    guides: list[dict] = []

    driver = _build_driver(headless=True)
    try:
        for category, listing_url in TARGETS.items():
            print(f"\nScraping {category} repair guides from {listing_url}")
            cards = _collect_symptom_cards(driver, listing_url)
            print(f"  Found {len(cards)} symptom cards")

            for idx, card in enumerate(cards, 1):
                print(f"  [{idx}/{len(cards)}] {card['name']}")
                detail = _scrape_detail(driver, card["url"])

                guides.append({
                    "category":    category,
                    "symptom":     card["name"],
                    "description": card["description"],
                    "frequency":   card["frequency"],
                    "parts":       detail["parts"],
                    "difficulty":  detail["difficulty"],
                    "video_url":   detail["video_url"],
                    "tips":        detail["tips"],
                    "url":         card["url"],
                })

                time.sleep(random.uniform(1.5, 3.0))

    finally:
        driver.quit()

    OUT_PATH.write_text(json.dumps(guides, indent=2, ensure_ascii=False), encoding="utf-8")

    fridge_c = sum(1 for g in guides if g["category"] == "refrigerator")
    dish_c   = sum(1 for g in guides if g["category"] == "dishwasher")
    print(f"\nSaved {len(guides)} repair guides to {OUT_PATH}")
    print(f"  Refrigerator: {fridge_c}  |  Dishwasher: {dish_c}")
    print(f"  With parts:   {sum(1 for g in guides if g['parts'])}")
    print(f"  With video:   {sum(1 for g in guides if g['video_url'])}")
    print("\nNext: python embed_and_index.py")


if __name__ == "__main__":
    main()

import os
import re
import time
import argparse
from typing import List, Dict, Optional

import pandas as pd
import requests
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from urllib.parse import quote


def slugify(text: str) -> str:
    text = text.strip().lower()
    allowed = []
    for c in text:
        if c.isalnum():
            allowed.append(c)
        elif c in [' ', '-', '_']:
            allowed.append('-')
        # ignore other characters like () , . |
    slug = ''.join(allowed)
    while '--' in slug:
        slug = slug.replace('--', '-')
    return slug.strip('-')


def normalize_for_match(text: str) -> str:
    """
    Normalize text for robust substring matching:
    - Lowercase
    - Remove all non-alphanumeric characters (including spaces)
    This way, 'Master Chef' and 'MasterChef' both normalize to 'masterchef'.
    """
    if text is None:
        return ""
    return "".join(ch.lower() for ch in str(text) if ch.isalnum())

class BlinkitScraper:
    def __init__(self, headless: bool = False):
        self.base_url = "https://blinkit.com"
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 12)
        self.products: List[Dict] = []

    def _build_search_url(self, brand: str) -> str:
        # Encode spaces as %20 (not +)
        encoded = quote(brand, safe="")  # spaces -> %20
        return f"{self.base_url}/s/?q={encoded}"

    def _scroll_to_load_all(self, min_wait_between_scroll: float = 1.0, max_no_growth_rounds: int = 3) -> None:
        no_growth_rounds = 0
        last_count = 0
        while True:
            cards = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button'][id]")
            current_count = len(cards)
            if current_count == last_count:
                no_growth_rounds += 1
            else:
                no_growth_rounds = 0
            last_count = current_count

            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(min_wait_between_scroll)

            if no_growth_rounds >= max_no_growth_rounds:
                break

    def search_and_collect_cards(self, brand: str) -> List[Dict]:
        url = self._build_search_url(brand)
        print(f"Opening: {url}")
        self.driver.get(url)

        # Wait for grid to appear (be tolerant to structure changes)
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.categories--with-search, div[class*='categories']"))
            )
        except TimeoutException:
            print("Search grid not found, continuing anyway...")
        time.sleep(2)

        # Load all products by scrolling
        self._scroll_to_load_all(min_wait_between_scroll=1.2, max_no_growth_rounds=3)

        cards = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button'][id]")
        print(f"Total product cards found: {len(cards)}")

        products: List[Dict] = []
        for card in cards:
            try:
                prod_id = card.get_attribute("id") or ""
                # Product title (best effort)
                title_text = ""
                try:
                    title_el = card.find_element(By.CSS_SELECTOR,
                        ".tw-text-300.tw-font-semibold, [class*='tw-font-semibold']")
                    title_text = title_el.text.strip()
                except NoSuchElementException:
                    pass

                # Price: look for exact class and validate rupee amount
                price_text = ""
                try:
                    rupee_pattern = re.compile(r"^\s*₹?\s*\d[\d,]*(?:\.\d+)?\s*$")
                    price_candidates = card.find_elements(By.CSS_SELECTOR, "div.tw-text-200.tw-font-semibold")
                    for el in price_candidates:
                        text_val = (el.text or "").strip()
                        if text_val and (text_val.startswith("₹") or rupee_pattern.match(text_val)):
                            price_text = text_val
                            break
                    # Fallback: any descendant that looks like a rupee value
                    if not price_text:
                        maybe_prices = card.find_elements(By.XPATH, ".//*[starts-with(normalize-space(text()), '₹') or matches(normalize-space(text()), '^\u20B9?\\s*\\d[\\d,]*(?:\\.\\d+)?$')]")
                        for el in maybe_prices:
                            text_val = (el.text or "").strip()
                            if text_val and (text_val.startswith("₹") or rupee_pattern.match(text_val)):
                                price_text = text_val
                                break
                except Exception:
                    pass

                # Pack size (best effort)
                pack_text = ""
                try:
                    pack_el = card.find_element(By.CSS_SELECTOR,
                        ".tw-text-200.tw-font-medium, [class*='font-medium']")
                    pack_text = pack_el.text.strip()
                except NoSuchElementException:
                    pass

                # ADD button availability -> availability hint
                in_stock = True
                try:
                    card.find_element(By.XPATH, ".//*[text()='ADD']")
                    in_stock = True
                except NoSuchElementException:
                    in_stock = False

                products.append({
                    "product_id": prod_id,
                    "title": title_text,
                    "price": price_text,
                    "pack": pack_text,
                    "in_stock": in_stock,
                })
            except Exception as e:
                print(f"Error reading card: {e}")
                continue

        self.products = products
        return products

    def _navigate_to_product_and_capture_url(self, card, timeout: float = 8.0) -> Optional[str]:
        # Try anchor first
        try:
            anchor = card.find_element(By.CSS_SELECTOR, "a[href*='/prn/'], a[href*='/product'], a[href^='https://blinkit.com']")
            href = anchor.get_attribute("href")
            if href:
                return href
        except NoSuchElementException:
            pass

        # Fallback: click card, wait for URL change to a product page, capture URL, then go back
        original_url = self.driver.current_url
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", card)
        except Exception:
            try:
                card.click()
            except Exception:
                return None

        # Wait for URL that contains /prn or /product
        end_time = time.time() + timeout
        captured = None
        while time.time() < end_time:
            current_url = self.driver.current_url
            if "/prn/" in current_url or "/product" in current_url:
                captured = current_url
                break
            time.sleep(0.2)

        # Return to search results page
        try:
            self.driver.back()
            # Wait for cards again
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='button'][id]")))
            time.sleep(0.5)
        except Exception:
            pass

        return captured

    def collect_product_links(self) -> List[Dict]:
        # Build product URLs deterministically from card id + title without clicking
        results: List[Dict] = []
        seen_urls = set()
        for idx, prod in enumerate(self.products, 1):
            title_text = (prod.get("title") or "").strip()
            prod_id = (prod.get("product_id") or "").strip()
            if not prod_id:
                print(f"Collecting link {idx}/{len(self.products)}: missing product id -> skipped")
                continue

            slug = slugify(title_text) if title_text else prod_id
            url = f"{self.base_url}/prn/{slug}/prid/{prod_id}"

            if url in seen_urls:
                print(f"Collecting link {idx}/{len(self.products)}: duplicate -> skipped")
                continue

            seen_urls.add(url)
            results.append({
                "Product URL": url,
                "Title": title_text,
                "Price": prod.get("price", ""),
                "Pack": prod.get("pack", ""),
                "In Stock": prod.get("in_stock", True)
            })

        print(f"Total unique product links captured: {len(results)}")
        return results

    def save_links_to_excel(self, rows: List[Dict], excel_path: str) -> str:
        if not rows:
            print("No rows to save")
            return excel_path

        df = pd.DataFrame(rows)
        target_dir = os.path.dirname(os.path.abspath(excel_path))
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        try:
            df.to_excel(excel_path, index=False, engine='openpyxl')
            print(f"Saved: {excel_path}")
            return excel_path
        except Exception as e:
            csv_path = os.path.splitext(excel_path)[0] + ".csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"Excel write failed ({e}). Saved CSV instead: {csv_path}")
            return csv_path

    def scrape_images_from_product(self, product_url: str) -> Dict:
        print(f"Opening product page: {product_url}")
        self.driver.get(product_url)

        # Wait for product carousel or main image to appear
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "section.carousel-content img, [class*='carousel-content'] img, img[src*='cdn.grofers.com']"))
            )
        except TimeoutException:
            print("  Product images not found, continuing")
        time.sleep(1.0)

        # Try to grab product title (best effort)
        product_title = ""
        title_selectors = [
            "h1",
            "[data-testid='PDPInfo-name']",
            "[class*='product'] h1",
            "[class*='tw-text-300'][class*='font-semibold']"
        ]
        for sel in title_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                text_val = el.text.strip()
                if text_val:
                    product_title = text_val
                    break
            except NoSuchElementException:
                continue

        # Collect thumbnails (radio buttons)
        thumb_selectors = [
            "section.sc-bjUoiL.ePzFFn.carousel-content img",
            "section.carousel-content img",
            "[class*='carousel-content'] img",
            "[class*='ProductCarousel__CarouselImage'] img, [class*='ProductCarousel__CarouselImage']",
        ]
        thumbnails = []
        for sel in thumb_selectors:
            els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                thumbnails = els
                break

        print(f"  Thumbnails found: {len(thumbnails)}")

        captured_urls: List[str] = []
        seen_urls = set()

        # Optionally expand product details if the toggle is present, then extract details
        product_details_text = ""
        key_features_text = ""

        def expand_details_if_present():
            try:
                # Try multiple XPaths that may match the toggle button
                toggle_candidates = self.driver.find_elements(
                    By.XPATH,
                    "//button[.//div[contains(normalize-space(.), 'View more details')] or contains(normalize-space(.), 'View more details') or contains(normalize-space(.), 'View product details') or .//span[contains(@class,'icon-down-triangle')]]"
                )
                for el in toggle_candidates:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        time.sleep(0.2)
                        el.click()
                        time.sleep(0.5)
                        break
                    except Exception:
                        continue
            except Exception:
                pass

        def extract_product_text():
            nonlocal product_details_text, key_features_text
            # Key Features text
            try:
                key_heading = None
                for xpath in [
                    "//div[contains(@class,'tw-text-300') and contains(normalize-space(.), 'Key Features')]",
                    "//*[contains(normalize-space(.), 'Key Features')]",
                ]:
                    els = self.driver.find_elements(By.XPATH, xpath)
                    if els:
                        key_heading = els[0]
                        break
                if key_heading is not None:
                    # The details may be in following sibling with regular font and pre-wrap
                    try:
                        desc = key_heading.find_element(By.XPATH, "following::div[contains(@class,'tw-whitespace-pre-wrap')][1]")
                        key_features_text = (desc.text or "").strip()
                    except Exception:
                        pass
            except Exception:
                pass

            # Product details/description
            detail_selectors = [
                "div.tw-text-200.tw-font-regular.tw-whitespace-pre-wrap",
                "[data-testid='PDPInfo-description']",
                "[class*='whitespace-pre-wrap']",
            ]
            for sel in detail_selectors:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    txt = (el.text or "").strip()
                    if txt:
                        product_details_text = txt
                        break
                except Exception:
                    continue

        expand_details_if_present()
        extract_product_text()

        def pick_main_image_url() -> Optional[str]:
            main_selectors = [
                "div[style*='cursor: crosshair'][style*='position: relative'] img[src*='cdn.grofers.com']",
                "img[src*='cdn.grofers.com'][src*='w=480']",
                "img[src*='/cms-assets/cms/product/']",
            ]
            for ms in main_selectors:
                try:
                    imgs = self.driver.find_elements(By.CSS_SELECTOR, ms)
                    for img in imgs:
                        src = img.get_attribute('src')
                        if src and ('/cms-assets/cms/product/' in src or 'da/cms-assets/cms/product/' in src or 'w=480' in src):
                            return src
                except Exception:
                    continue
            return None

        # If there are no thumbnails, try to capture main image only
        if not thumbnails:
            url = pick_main_image_url()
            if url:
                captured_urls.append(url)
            return {
                "product_title": product_title,
                "images": captured_urls,
            }

        # Click-through each thumbnail to swap main image, then capture main image url
        for idx, thumb in enumerate(thumbnails):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thumb)
                time.sleep(0.2)
                self.driver.execute_script("arguments[0].click();", thumb)
            except Exception:
                try:
                    thumb.click()
                except Exception:
                    pass
            time.sleep(0.8)

            main_url = pick_main_image_url()
            if main_url and main_url not in seen_urls:
                seen_urls.add(main_url)
                captured_urls.append(main_url)
                print(f"    Captured image {len(captured_urls)}: {main_url}")
            else:
                # As fallback, use the thumbnail src and try to upscale w=120 to w=480
                try:
                    thumb_src = thumb.get_attribute('src')
                    if thumb_src:
                        alt_url = thumb_src
                        # Blinkit thumbnails often have w=120,h=120; upscale to 480
                        alt_url = alt_url.replace(",w=120", ",w=480").replace(",h=120", ",h=480")
                        alt_url = alt_url.replace("w=120", "w=480").replace("h=120", "h=480")
                        if alt_url not in seen_urls:
                            seen_urls.add(alt_url)
                            captured_urls.append(alt_url)
                            print(f"    Fallback image {len(captured_urls)}: {alt_url}")
                except Exception:
                    pass

        return {
            "product_title": product_title,
            "images": captured_urls,
            "product_details": product_details_text,
            "key_features": key_features_text,
        }

       
    def download_images(self, images: List[str], base_dir: str, brand: str, product_title: str, product_url: str, index: int) -> str:
        # Prepare directory compatible with downstream agents (product_XXX_Title)
        safe_title = product_title or f"product_{index}"
        safe_title = ''.join(c for c in safe_title if c.isalnum() or c in [' ', '-', '_']).strip().replace(' ', '_')
        folder = os.path.join(base_dir, f"product_{index:03d}_{safe_title}")
        os.makedirs(folder, exist_ok=True)

        for i, url in enumerate(images, 1):
            try:
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    # Normalize to JPEG for compatibility
                    try:
                        img = Image.open(BytesIO(resp.content))
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        fname = os.path.join(folder, f"image_{i}.jpg")
                        img.save(fname, format="JPEG", quality=92)
                        print(f"      Saved: {fname}")
                    except Exception:
                        fname = os.path.join(folder, f"image_{i}.jpg")
                        with open(fname, 'wb') as fh:
                            fh.write(resp.content)
                        print(f"      Saved (raw): {fname}")
            except Exception as e:
                print(f"      Failed to download image {i}: {e}")

        # Write product info for downstream agents
        try:
            info_path = os.path.join(folder, "product_info.txt")
            with open(info_path, "w", encoding="utf-8") as fh:
                fh.write(f"Product Title: {product_title}\n")
                fh.write(f"Product URL: {product_url}\n")
                fh.write(f"Product Index: {index}\n")
                fh.write(f"Scraped on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception:
            pass

        return folder

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Blinkit product scraper")
    parser.add_argument(
        "--brand",
        required=True,
        nargs="+",
        help="Brand or query to search (can contain spaces; quotes optional; spaces will be encoded as %20)",
    )
    parser.add_argument("--out-dir", default=os.path.join(os.getcwd(), "output"), help="Output directory for Excel and images")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("--images", action="store_true", help="Also open each product and scrape/download images")
    args = parser.parse_args()

    # Support multi-word brand names without requiring quotes
    brand = " ".join(args.brand).strip() if isinstance(args.brand, list) else str(args.brand).strip()
    out_dir = os.path.abspath(args.out_dir)
    brand_underscore = brand.replace(' ', '_')
    excel_path = os.path.join(out_dir, f"blinkit_{brand_underscore}_links.xlsx")
    products_excel_path = os.path.join(out_dir, f"blinkit_{brand_underscore}_products.xlsx")

    scraper = BlinkitScraper(headless=args.headless)
    try:
        print(f"Searching Blinkit for: {brand}")
        scraper.search_and_collect_cards(brand)
        rows = scraper.collect_product_links()
        saved_links_path = scraper.save_links_to_excel(rows, excel_path)

        # Create a brand-filtered links file where Title contains the brand (case-insensitive)
        filtered_links_path = None
        try:
            df_all = None
            if saved_links_path.lower().endswith('.xlsx'):
                df_all = pd.read_excel(saved_links_path)
            else:
                df_all = pd.read_csv(saved_links_path)
        except Exception:
            alt_csv = os.path.splitext(saved_links_path)[0] + '.csv'
            alt_xlsx = os.path.splitext(saved_links_path)[0] + '.xlsx'
            if os.path.exists(alt_csv):
                df_all = pd.read_csv(alt_csv)
            elif os.path.exists(alt_xlsx):
                df_all = pd.read_excel(alt_xlsx)
            else:
                df_all = None

        if df_all is not None and not df_all.empty and 'Title' in df_all.columns:
            # Flexible matching: direct case-insensitive contains OR normalized contains
            titles_series = df_all['Title'].astype(str)
            norm_titles = titles_series.apply(normalize_for_match)
            norm_brand = normalize_for_match(brand)
            # Escape regex in brand for the direct contains check
            direct_mask = titles_series.str.contains(re.escape(brand), case=False, na=False)
            normalized_mask = norm_titles.str.contains(norm_brand, na=False)
            mask = direct_mask | normalized_mask
            df_filtered = df_all.loc[mask].copy()
            filtered_path_xlsx = os.path.join(out_dir, f"blinkit_{brand_underscore}_links_filtered.xlsx")
            try:
                df_filtered.to_excel(filtered_path_xlsx, index=False, engine='openpyxl')
                filtered_links_path = filtered_path_xlsx
                print(f"Saved filtered links: {filtered_path_xlsx}")
            except Exception as e:
                filtered_path_csv = os.path.splitext(filtered_path_xlsx)[0] + '.csv'
                df_filtered.to_csv(filtered_path_csv, index=False, encoding='utf-8-sig')
                filtered_links_path = filtered_path_csv
                print(f"Filtered Excel write failed ({e}). Saved CSV instead: {filtered_path_csv}")

            # Also create filtered_products.xlsx expected by downstream agents
            try:
                df_expected = df_filtered.rename(columns={"Title": "title", "Product URL": "url"})
                cols = [c for c in ["title", "url"] if c in df_expected.columns]
                df_expected = df_expected[cols]
                expected_path = os.path.join(out_dir, f"{brand_underscore}_filtered_products.xlsx")
                df_expected.to_excel(expected_path, index=False, engine='openpyxl')
                print(f"Created downstream file: {expected_path}")
            except Exception as e:
                print(f"Failed to create filtered_products.xlsx: {e}")

        if args.images:
            print("\nScraping images for each product...")
            enriched_rows = []

            # Read back URLs from the filtered links file if available; otherwise fall back to all links
            df_links = None
            source_path = filtered_links_path if 'filtered_links_path' in locals() and filtered_links_path else saved_links_path
            try:
                if source_path.lower().endswith('.xlsx'):
                    df_links = pd.read_excel(source_path)
                else:
                    df_links = pd.read_csv(source_path)
            except Exception:
                # Attempt alternate extension if needed
                alt_csv = os.path.splitext(source_path)[0] + '.csv'
                if os.path.exists(alt_csv):
                    df_links = pd.read_csv(alt_csv)
                else:
                    alt_xlsx = os.path.splitext(source_path)[0] + '.xlsx'
                    if os.path.exists(alt_xlsx):
                        try:
                            df_links = pd.read_excel(alt_xlsx)
                        except Exception:
                            df_links = None

            if df_links is None or df_links.empty:
                print("No links found in saved file; aborting image scrape.")
            else:
                for idx, row in enumerate(df_links.to_dict(orient='records'), 1):
                    url = row.get("Product URL")
                    if not isinstance(url, str) or not url.strip():
                        continue
                    details = scraper.scrape_images_from_product(url.strip())
                    images = details.get("images", [])
                    title = details.get("product_title") or row.get("Title", "")
                    prod_details = details.get("product_details", "")
                    key_features = details.get("key_features", "")
                    # Download images into product_XXX_Title folder under out_dir
                    scraper.download_images(images, base_dir=out_dir, brand=brand, product_title=title, product_url=url.strip(), index=idx)
                    enriched = dict(row)
                    enriched["Product Title (PDP)"] = title
                    enriched["Image URLs"] = " | ".join(images)
                    enriched["Num Images"] = len(images)
                    enriched["Product Details"] = prod_details
                    enriched["Key Features"] = key_features
                    enriched_rows.append(enriched)

                # Save enriched rows with image URLs and product info
                if enriched_rows:
                    target_out_path = filtered_links_path if 'filtered_links_path' in locals() and filtered_links_path else products_excel_path
                    scraper.save_links_to_excel(enriched_rows, target_out_path)
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

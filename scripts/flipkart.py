import time
import os
import sys
import argparse
import requests
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

# Make printing robust on Windows consoles that do not support emojis/UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# NOTE: HOTFOLDER_PATH and BRAND_KEYWORD will be set from CLI args in main()
HOTFOLDER_PATH = ""
BRAND_KEYWORD = ""

# Try undetected_chromedriver first, fallback to regular selenium
driver = None
try:
    if UC_AVAILABLE:
        options = uc.ChromeOptions()
        options.headless = False  # Set to True for headless
        options.add_argument('--start-maximized')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        # Try to use existing Chrome installation
        try:
            driver = uc.Chrome(options=options, version_main=None)
            print("✅ Using undetected_chromedriver")
        except Exception as e:
            print(f"⚠️ Undetected_chromedriver failed: {e}")
            driver = None
   
    if driver is None:
        # Fallback to regular selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument('--start-maximized')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        driver = webdriver.Chrome(options=options)
        print("✅ Using regular selenium webdriver")
       
except Exception as e:
    print(f"❌ Failed to initialize Chrome driver: {e}")
    exit(1)

# --- Flipkart product scraping ---

def main():
    global HOTFOLDER_PATH, BRAND_KEYWORD
    # CLI args
    parser = argparse.ArgumentParser(description="Flipkart product scraper")
    parser.add_argument("--brand", required=True, help="Brand keyword to search")
    parser.add_argument("--out-dir", default=os.path.join(os.getcwd(), "output"), help="Output directory for Excel and images")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (if supported)")
    args = parser.parse_args()

    BRAND_KEYWORD = args.brand.strip()
    HOTFOLDER_PATH = os.path.abspath(args.out_dir)
    os.makedirs(HOTFOLDER_PATH, exist_ok=True)
    brand_underscore = BRAND_KEYWORD.replace(' ', '_')
    try:
        # Go to Flipkart
        driver.get("https://www.flipkart.com")
        time.sleep(5)

        # Handle any popups or login modals
        try:
            # Close login popup if it appears
            close_popup = driver.find_element(By.CSS_SELECTOR, "button._2KpZ6l._2doB4z")
            close_popup.click()
            print("✅ Closed login popup")
            time.sleep(2)
        except:
            print("No login popup found or already closed")

        # Search for brand using the provided CSS selector
        try:
            search_box = driver.find_element(By.CSS_SELECTOR, "input.Pke_EE")
            search_box.clear()
            search_box.send_keys(BRAND_KEYWORD)
            search_box.send_keys(Keys.RETURN)
            print(f"✅ Search executed successfully for {BRAND_KEYWORD}")
            time.sleep(5)
        except Exception as e:
            print(f"❌ Failed to find search box: {e}")
            # Try alternative selectors
            try:
                search_box = driver.find_element(By.NAME, "q")
                search_box.clear()
                search_box.send_keys(BRAND_KEYWORD)
                search_box.send_keys(Keys.RETURN)
                print("✅ Search executed with alternative selector")
                time.sleep(5)
            except Exception as e2:
                print(f"❌ Failed with alternative selector: {e2}")
                raise Exception("Could not find search box")

        # Extract all product links and titles from all pages (handle pagination)
        all_product_data = []  # Will store dicts with link and title
        page_number = 1
       
        while True:
            print(f"\n📄 Processing page {page_number}...")
           
            # Scroll and wait for products to load on current page
            print("📜 Scrolling to load products...")
            for i in range(3):
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(1)
           
            # Wait for search results to load
            time.sleep(3)
            print(f"Current URL: {driver.current_url}")

            # Extract product links and titles from current page using correct selectors
            page_product_data = []
           
            # Find all product containers with data-id attributes
            try:
                # Look for product containers in the main results area
                product_containers = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
                print(f"Found {len(product_containers)} product containers on page {page_number}")
               
                for container in product_containers:
                    try:
                        # Find the product link within each container
                        # Try multiple selectors for product links
                        product_link = None
                        selectors_to_try = [
                            "a[title]",  # Primary selector
                            "a[href*='/p/']",  # Alternative selector
                            ".XeoURe a",  # Based on the HTML structure
                            ".MrGHbB a"   # Another alternative
                        ]
                       
                        for selector in selectors_to_try:
                            try:
                                product_link = container.find_element(By.CSS_SELECTOR, selector)
                                break
                            except:
                                continue
                       
                        if product_link:
                            href = product_link.get_attribute("href")
                            title = product_link.get_attribute("title") or "Unknown Product"
                           
                            if href and href.startswith("https://www.flipkart.com") and "/p/" in href:
                                # Avoid duplicates - check if this URL already exists
                                existing_urls = [item['product_link'] for item in page_product_data]
                                if href not in existing_urls:
                                    page_product_data.append({
                                        'product_link': href,
                                        'product_title': title
                                    })
                                    print(f"  ✅ Found: {title[:50]}...")
                           
                    except Exception as e:
                        # Skip containers without valid product links
                        pass
                       
            except Exception as e:
                print(f"❌ Error finding product containers: {e}")
               
                # Fallback: try old selector method
                try:
                    print("🔄 Trying fallback selector method...")
                    fallback_anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/p/']")
                    for a in fallback_anchors:
                        href = a.get_attribute("href")
                        title = a.get_attribute("title") or "Unknown Product"
                       
                        if href and href.startswith("https://www.flipkart.com") and "/p/" in href:
                            existing_urls = [item['product_link'] for item in page_product_data]
                            if href not in existing_urls:
                                page_product_data.append({
                                    'product_link': href,
                                    'product_title': title
                                })
                                print(f"  ✅ Fallback found: {title[:50]}...")
                except Exception as e2:
                    print(f"❌ Fallback method also failed: {e2}")
               
            print(f"📦 Found {len(page_product_data)} products on page {page_number}")
            all_product_data.extend(page_product_data)
           
            # Check for pagination - look for "Next" button
            pagination_found = False
            try:
                # Try multiple selectors for pagination
                pagination_selectors = [
                    "a._9QVEpD",  # Primary selector
                    "a[aria-label='Next']",  # Alternative
                    "nav a:contains('Next')",  # Another alternative
                    ".cPHDOP a[href*='page=']"  # Generic page link
                ]
               
                for selector in pagination_selectors:
                    try:
                        if "contains" in selector:
                            # Skip XPath-like selectors for now
                            continue
                           
                        next_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                       
                        for next_button in next_buttons:
                            try:
                                # Check if this is actually a "Next" button
                                button_text = ""
                               
                                # Try to get text from span inside
                                try:
                                    span = next_button.find_element(By.TAG_NAME, "span")
                                    button_text = span.text.strip().lower()
                                except:
                                    # Try direct text
                                    button_text = next_button.text.strip().lower()
                               
                                # Check href for page indication
                                href = next_button.get_attribute("href") or ""
                               
                                if ("next" in button_text or
                                    (f"page={page_number + 1}" in href and "page=" in href)):
                                   
                                    print(f"🔄 Found 'Next' button, navigating to page {page_number + 1}...")
                                    print(f"   Button text: '{button_text}', href: {href[:100]}...")
                                   
                                    # Scroll to button first
                                    driver.execute_script("arguments[0].scrollIntoView();", next_button)
                                    time.sleep(1)
                                   
                                    # Click the next button
                                    driver.execute_script("arguments[0].click();", next_button)
                                    time.sleep(5)  # Wait for next page to load
                                   
                                    pagination_found = True
                                    page_number += 1
                                    break
                                   
                            except Exception as e:
                                continue
                               
                        if pagination_found:
                            break
                           
                    except Exception as e:
                        continue
                       
                if not pagination_found:
                    print("📄 No more pages to process")
                    break
                   
            except Exception as e:
                print(f"📄 No pagination found or end of results: {e}")
                break
               
            # Safety check to prevent infinite loops
            if page_number > 10:  # Max 10 pages
                print("⚠️ Reached maximum page limit (10 pages)")
                break
       
        print(f"\n🔗 Total found {len(all_product_data)} products across {page_number} page(s).")

        # Save product data to Excel
        if all_product_data:
            df_products = pd.DataFrame(all_product_data)
            excel_path = os.path.join(HOTFOLDER_PATH, f"flipkart_{brand_underscore}_links.xlsx")
            df_products.to_excel(excel_path, index=False)
            print(f"📝 Product data saved to: {excel_path}")
            print(f"   Columns: {list(df_products.columns)}")

            # 1) Create a second Excel with rows where the brand keyword appears in product_title
            df_brand = df_products[df_products['product_title'].str.contains(BRAND_KEYWORD, case=False, na=False)].copy()
            brand_excel_path = os.path.join(HOTFOLDER_PATH, f"flipkart_{brand_underscore}_links_filtered.xlsx")
            df_brand.to_excel(brand_excel_path, index=False)
            print(f"📝 Brand-filtered product data saved to: {brand_excel_path}")

            # 1b) Create filtered_products.xlsx expected by downstream agents
            try:
                df_expected = df_brand.rename(columns={
                    'product_title': 'title',
                    'product_link': 'url'
                })
                keep_cols = [c for c in ['title', 'url'] if c in df_expected.columns]
                df_expected = df_expected[keep_cols]
                expected_path = os.path.join(HOTFOLDER_PATH, f"{brand_underscore}_filtered_products.xlsx")
                df_expected.to_excel(expected_path, index=False)
                print(f"📝 Created downstream file: {expected_path}")
            except Exception as e:
                print(f"⚠️ Failed to create filtered_products.xlsx: {e}")

            # 2) Scrape images only for the filtered list
            print("\n🔄 Reading brand-filtered list and scraping images from each matching product...")
            for idx, row in df_brand.reset_index(drop=True).iterrows():
                product_url = row['product_link']
                product_title = row['product_title']
               
                try:
                    print(f"\n🛒 Processing product {idx+1}/{len(df_brand)}")
                    print(f"Title: {product_title}")
                    print(f"URL: {product_url}")
                    driver.get(product_url)
                    time.sleep(4)
                    # Prepare per-product folder compatible with downstream: product_XXX_Title under out-dir
                    safe_title = ''.join(c for c in product_title if c.isalnum() or c in [' ', '-', '_']).strip().replace(' ', '_')
                    product_folder = os.path.join(HOTFOLDER_PATH, f"product_{idx+1:03d}_{safe_title}")
                    os.makedirs(product_folder, exist_ok=True)

                    # Write product info file
                    try:
                        info_path = os.path.join(product_folder, "product_info.txt")
                        with open(info_path, 'w', encoding='utf-8') as fh:
                            fh.write(f"Product Title: {product_title}\n")
                            fh.write(f"Product URL: {product_url}\n")
                            fh.write(f"Product Index: {idx+1}\n")
                            fh.write(f"Scraped on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    except Exception:
                        pass

                    # Helpers
                    def extract_best_image_url():
                        js = """
                        const imgs = Array.from(document.querySelectorAll('img'));
                        let best = null;
                        let bestScore = 0;
                        for (const img of imgs) {
                          const rect = img.getBoundingClientRect();
                          const visible = rect.width > 80 && rect.height > 80 && rect.bottom > 0 && rect.top < (window.innerHeight + 200);
                          const src = img.currentSrc || img.src || '';
                          if (!visible) continue;
                          if (!src) continue;
                          if (!/rukminim|flipkart|fkcdn/i.test(src)) continue;
                          const score = rect.width * rect.height;
                          if (score > bestScore) {
                            best = { src, srcset: img.srcset || '', w: rect.width, h: rect.height };
                            bestScore = score;
                          }
                        }
                        return best;
                        """
                        try:
                            best = driver.execute_script(js)
                        except Exception:
                            best = None
                        if not best:
                            return None
                        # prefer highest res in srcset
                        final_url = best.get('src')
                        srcset = best.get('srcset') or ''
                        if srcset:
                            parts = [p.strip() for p in srcset.split(',') if p.strip()]
                            if parts:
                                final_url = parts[-1].split(' ')[0]
                        return final_url

                    def get_main_image_url():
                        """Return the current main product image URL (prefer highest-res from srcset)."""
                        js = """
                        const selectors = [
                          'div._8id3KM img.DByuf4',
                          'div._8id3KM img',
                          'img.DByuf4',
                          'img[class*="DByuf4"]',
                          'img[src*="flipkart.com/image/"]'
                        ];
                        let img = null;
                        for (const sel of selectors) {
                          const el = document.querySelector(sel);
                          if (el) { img = el; break; }
                        }
                        if (!img) return null;
                        const rect = img.getBoundingClientRect();
                        const src = img.currentSrc || img.src || '';
                        const srcset = img.srcset || '';
                        return { src, srcset, w: rect.width, h: rect.height };
                        """
                        try:
                            info = driver.execute_script(js)
                        except Exception:
                            info = None
                        if not info:
                            return None
                        final_url = info.get('src')
                        srcset = info.get('srcset') or ''
                        if srcset:
                            parts = [p.strip() for p in srcset.split(',') if p.strip()]
                            if parts:
                                final_url = parts[-1].split(' ')[0]
                        return final_url

                    # 3) Traverse thumbnails via ul/li structure to capture ALL images
                    images_saved_count = 0
                    seen_image_urls = set()

                    # Try robustly to locate li thumbnails under a ul container
                    li_candidates = []
                    try:
                        # Primary: UL with known class then LIs
                        li_candidates = driver.find_elements(By.CSS_SELECTOR, "ul.ZqtVYK li")
                    except Exception:
                        li_candidates = []

                    if not li_candidates:
                        try:
                            # XPath: any UL that contains div.HXf4Qp then get its LIs
                            li_candidates = driver.find_elements(
                                By.XPATH,
                                "//ul[.//div[contains(@class,'HXf4Qp')]]//li"
                            )
                        except Exception:
                            li_candidates = []

                    if not li_candidates:
                        try:
                            # Fallback: find the small thumbnail divs and go up to their LI parents
                            thumb_divs = driver.find_elements(By.CSS_SELECTOR, "div.HXf4Qp")
                            for d in thumb_divs:
                                try:
                                    li = d.find_element(By.XPATH, "ancestor::li[1]")
                                    li_candidates.append(li)
                                except Exception:
                                    continue
                        except Exception:
                            pass

                    print(f"Found {len(li_candidates)} li thumbnail items")

                    if li_candidates:

                        for thumb_idx, li_node in enumerate(li_candidates, 1):
                            try:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", li_node)
                                time.sleep(0.3)
                                # Click the thumbnail image inside li if present, else the li itself
                                try:
                                    # Prefer the small thumbnail image element for a proper click
                                    clickable = li_node.find_element(By.CSS_SELECTOR, "img._0DkuPH, img")
                                except Exception:
                                    try:
                                        clickable = li_node.find_element(By.CSS_SELECTOR, "div.HXf4Qp")
                                    except Exception:
                                        clickable = li_node
                                # Capture current main image before clicking this thumbnail
                                prev_main_url = get_main_image_url() or extract_best_image_url()

                                # Try a real click first, then fallback to JS click
                                try:
                                    ActionChains(driver).move_to_element(clickable).pause(0.05).click(on_element=clickable).perform()
                                except Exception:
                                    driver.execute_script("arguments[0].click();", clickable)

                                # Wait for the main image URL to change from previous
                                max_attempts = 20
                                current_image_url = None

                                for attempt in range(max_attempts):
                                    time.sleep(0.4)
                                    current_image_url = get_main_image_url() or extract_best_image_url()
                                    # Break when we have a URL and it differs from the previous one
                                    if current_image_url:
                                        if not prev_main_url or current_image_url != prev_main_url:
                                            break

                                if not current_image_url:
                                    print(f"⚠️ No image URL detected for thumbnail {thumb_idx}")
                                    continue

                                # Skip duplicates if the URL hasn't changed across thumbnails
                                if current_image_url in seen_image_urls:
                                    print(f"↩️ Skipping duplicate image for thumbnail {thumb_idx}")
                                    continue

                                # Save image
                                try:
                                    response = requests.get(current_image_url, timeout=12, headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
                                        'Referer': product_url
                                    })
                                    filename = f"image_{thumb_idx}.jpg"
                                    img_path = os.path.join(product_folder, filename)
                                    with open(img_path, 'wb') as f:
                                        f.write(response.content)
                                    images_saved_count += 1
                                    seen_image_urls.add(current_image_url)
                                    print(f"✅ Saved image {thumb_idx} -> {img_path}")
                                except Exception as e_dl:
                                    print(f"❌ Failed to download image {thumb_idx}: {e_dl}")

                            except Exception as e:
                                print(f"❌ Failed to process li thumbnail {thumb_idx}: {e}")

                        # Fallback: if nothing captured, attempt to use thumbnail src values directly
                        if images_saved_count == 0:
                            try:
                                thumb_imgs = driver.find_elements(By.CSS_SELECTOR, "ul.ZqtVYK li img, div.HXf4Qp img, li img")
                                for t_i, t in enumerate(thumb_imgs, 1):
                                    src = t.get_attribute('src') or ''
                                    srcset = t.get_attribute('srcset') or ''
                                    if srcset:
                                        parts = [p.strip() for p in srcset.split(',') if p.strip()]
                                        if parts:
                                            src = parts[-1].split(' ')[0]
                                    if src and src not in seen_image_urls:
                                        try:
                                            response = requests.get(src, timeout=12, headers={
                                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
                                                'Referer': product_url
                                            })
                                            filename = f"image_thumb_{t_i}.jpg"
                                            img_path = os.path.join(product_folder, filename)
                                            with open(img_path, 'wb') as f:
                                                f.write(response.content)
                                            images_saved_count += 1
                                            seen_image_urls.add(src)
                                            print(f"✅ Saved fallback thumbnail {t_i} -> {img_path}")
                                        except Exception as e_dl2:
                                            print(f"❌ Failed to download fallback thumbnail {t_i}: {e_dl2}")
                            except Exception:
                                pass

                        # Note: intentionally skipping additional dedupe branch for simplicity
                    else:
                        # If no li thumbnails, try to get the main product image directly as a fallback
                        try:
                            main_image_url = get_main_image_url() or extract_best_image_url()
                            if main_image_url:
                                response = requests.get(main_image_url, timeout=12, headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
                                    'Referer': product_url
                                })
                                filename = "image_1.jpg"
                                img_path = os.path.join(product_folder, filename)
                                with open(img_path, 'wb') as f:
                                    f.write(response.content)
                                print(f"✅ Saved main image -> {img_path}")
                            else:
                                print("❌ No main image URL found")
                        except Exception as e:
                            print(f"❌ Failed to get main image: {e}")

                    time.sleep(2)  # Small delay between products

                except Exception as e:
                    print(f"❌ Failed to process product {idx+1}: {e}")
                    continue
        else:
            print("❌ No products found to save")

    except Exception as e:
        print(f"❌ Main execution error: {e}")

    finally:
        if driver:
            # Check if we should keep driver alive for other agents
            keep_alive = os.environ.get('KEEP_BROWSER_ALIVE', 'false').lower() == 'true'
            if not keep_alive:
                driver.quit()
                print(f"\n🎉 Flipkart {BRAND_KEYWORD} products processed successfully!")
            else:
                print(f"\n🎉 Flipkart {BRAND_KEYWORD} products processed successfully!")
                print("🔄 Keeping browser alive for other agents...")
                return driver

if __name__ == '__main__':
    main() 
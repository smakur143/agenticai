import time
import argparse
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import os
from urllib.parse import urljoin, quote_plus
import json

class ZeptoScraper:
    def __init__(self, headless=False):
        """Initialize the Zepto scraper with Chrome driver"""
        self.driver = None
        self.base_url = "https://www.zeptonow.com"
        self.setup_driver(headless)
        self.products_data = []
       
    def setup_driver(self, headless=False):
        """Setup Chrome driver with necessary options"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
       
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            print("Chrome driver initialized successfully")
        except Exception as e:
            print(f"Error initializing Chrome driver: {e}")
            print("Please make sure you have Chrome and ChromeDriver installed")
           
    def search_products(self, search_query):
        """Search for products and get all product links by scrolling"""
        # Format search query for URL (replace spaces with +)
        formatted_query = quote_plus(search_query)
        search_url = f"{self.base_url}/search?query={formatted_query}"
       
        print(f"Searching for: {search_query}")
        print(f"URL: {search_url}")
       
        self.driver.get(search_url)
        time.sleep(3)
       
        # Wait for the products grid to load
        try:
            products_grid = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "div.grid.w-full.gap-x-3.gap-y-5.overflow-x-hidden"))
            )
        except TimeoutException:
            print("Products grid not found")
            return []
       
        product_links = []
        last_height = self.driver.execute_script("return document.body.scrollHeight")
       
        while True:
            # Scroll down slowly to load more products
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for new products to load
           
            # Check if new content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("Reached end of products")
                break
            last_height = new_height
           
            # Get current product links
            current_links = self.driver.find_elements(By.CSS_SELECTOR,
                "a[href*='/pn/']")
            print(f"Found {len(current_links)} product links so far...")
       
        # Extract all product links and stock status
        product_elements = self.driver.find_elements(By.CSS_SELECTOR,
            "a[href*='/pn/']")
       
        for element in product_elements:
            try:
                link = element.get_attribute('href')
               
                # Check stock status
                container = element.find_element(By.CSS_SELECTOR,
                    "div[data-is-out-of-stock]")
                is_out_of_stock = container.get_attribute('data-is-out-of-stock')
               
                if link and link not in [p['url'] for p in product_links]:
                    product_links.append({
                        'url': link,
                        'out_of_stock': is_out_of_stock
                    })
            except NoSuchElementException:
                continue
               
        print(f"Total unique products found: {len(product_links)}")
        return product_links
   
    def scrape_product_details(self, product_url, out_of_stock_status):
        """Scrape detailed information from a product page"""
        print(f"Scraping product: {product_url}")
       
        self.driver.get(product_url)
        time.sleep(3)
       
        product_data = {
            'url': product_url,
            'out_of_stock': out_of_stock_status,
            'images': [],
            'product_info': {}
        }
       
        try:
            # Get product name and basic info
            try:
                product_name = self.driver.find_element(By.CSS_SELECTOR,
                    "h1, [data-slot-id='ProductName'], .product-name").text
                product_data['product_name'] = product_name
            except NoSuchElementException:
                product_data['product_name'] = "N/A"
           
            # Get price information
            try:
                price_element = self.driver.find_element(By.CSS_SELECTOR,
                    "[data-slot-id='Price'], .price")
                product_data['price'] = price_element.text
            except NoSuchElementException:
                product_data['price'] = "N/A"
           
            # Get pack size
            try:
                pack_size = self.driver.find_element(By.CSS_SELECTOR,
                    "[data-slot-id='PackSize'], .pack-size").text
                product_data['pack_size'] = pack_size
            except NoSuchElementException:
                product_data['pack_size'] = "N/A"
           
            # Get rating
            try:
                rating = self.driver.find_element(By.CSS_SELECTOR,
                    ".rating, [class*='rating']").text
                product_data['rating'] = rating
            except NoSuchElementException:
                product_data['rating'] = "N/A"
           
            # Scrape all images by clicking through image preview buttons
            image_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                "button[aria-label*='image-preview']")
           
            print(f"Found {len(image_buttons)} image preview buttons")
           
            # Use a more sophisticated approach to track unique images
            captured_image_ids = set()  # Track unique image identifiers
            all_possible_urls = set()   # Track all URL variations we've seen
           
            for i, button in enumerate(image_buttons):
                try:
                    print(f"\n--- Processing image button {i+1}/{len(image_buttons)} ---")
                   
                    # Click the image preview button
                    self.driver.execute_script("arguments[0].click();", button)
                    time.sleep(3)  # Wait for image to load completely
                   
                    # Collect all possible image URLs for this button
                    potential_urls = []
                   
                    # Strategy 1: Get from main image display
                    main_image_selectors = [
                        "img[data-nimg='fill']",
                        "img[fetchpriority='high']",
                        "img[fetchpriority='low']",
                        "img[decoding='sync']",
                        "img[decoding='async']",
                        "img[class*='relative'][class*='overflow-hidden']"
                    ]
                   
                    for selector in main_image_selectors:
                        try:
                            img_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for img_elem in img_elements:
                                src = img_elem.get_attribute('src')
                                if src and 'cms/product_variant' in src:
                                    potential_urls.append(('main_display', src))
                               
                                # Also check srcset
                                srcset = img_elem.get_attribute('srcset')
                                if srcset:
                                    for entry in srcset.split(','):
                                        url = entry.strip().split(' ')[0]
                                        if url and 'cms/product_variant' in url:
                                            potential_urls.append(('srcset', url))
                        except:
                            continue
                   
                    # Strategy 2: Get from button thumbnail itself
                    try:
                        button_img = button.find_element(By.CSS_SELECTOR, "img")
                        button_src = button_img.get_attribute('src')
                        if button_src and 'cms/product_variant' in button_src:
                            potential_urls.append(('button_thumb', button_src))
                           
                            # Create high-res versions
                            if 'tr:w-88' in button_src:
                                high_res = button_src.replace('tr:w-88', 'tr:w-1280')
                                potential_urls.append(('button_high_res', high_res))
                           
                            # Extract base image ID for comparison
                            if '/cms/product_variant/' in button_src:
                                parts = button_src.split('/cms/product_variant/')
                                if len(parts) > 1:
                                    image_id = parts[1].split('/')[0]  # Get the UUID part
                                    base_url = f"{parts[0]}/cms/product_variant/{image_id}"
                                   
                                    # Generate different resolution versions
                                    variations = [
                                        f"{base_url}.jpeg",
                                        f"{parts[0]}/production/tr:w-1280,ar-3000-3000,pr-true,f-auto,q-80/cms/product_variant/{image_id}.jpeg",
                                        f"{parts[0]}/production/ik-seo/tr:w-1280,ar-3000-3000,pr-true,f-auto,q-80/cms/product_variant/{image_id}/",
                                    ]
                                   
                                    for var_url in variations:
                                        potential_urls.append(('generated', var_url))
                    except:
                        pass
                   
                    print(f"Found {len(potential_urls)} potential URLs for button {i+1}")
                   
                    # Now select the best URL that we haven't captured yet
                    selected_url = None
                    selected_type = None
                   
                    # Priority order: main_display > button_high_res > generated > srcset > button_thumb
                    priority_order = ['main_display', 'button_high_res', 'generated', 'srcset', 'button_thumb']
                   
                    for url_type in priority_order:
                        for source_type, url in potential_urls:
                            if source_type == url_type and url not in all_possible_urls:
                                # Extract image identifier for uniqueness check
                                if '/cms/product_variant/' in url:
                                    parts = url.split('/cms/product_variant/')
                                    if len(parts) > 1:
                                        image_id = parts[1].split('/')[0].split('.')[0]  # Get UUID without extension
                                       
                                        if image_id not in captured_image_ids:
                                            selected_url = url
                                            selected_type = source_type
                                            captured_image_ids.add(image_id)
                                            break
                        if selected_url:
                            break
                   
                    # If we found a unique image, save it
                    if selected_url:
                        all_possible_urls.add(selected_url)
                        product_data['images'].append({
                            'image_index': i,
                            'image_url': selected_url,
                            'source_type': selected_type
                        })
                        print(f"✅ Captured image {i+1} [{selected_type}]: {selected_url}")
                    else:
                        # Force capture even if duplicate, but mark it
                        if potential_urls:
                            fallback_url = potential_urls[0][1]  # Take the first available URL
                            product_data['images'].append({
                                'image_index': i,
                                'image_url': fallback_url,
                                'source_type': 'duplicate_fallback'
                            })
                            print(f"⚠️ Captured duplicate image {i+1}: {fallback_url}")
                        else:
                            print(f"❌ No image found for button {i+1}")
                       
                except Exception as e:
                    print(f"❌ Error processing button {i+1}: {e}")
                    continue
           
            print(f"\n🎯 Total unique images captured: {len([img for img in product_data['images'] if img.get('source_type') != 'duplicate_fallback'])}")
            print(f"📸 Total images including duplicates: {len(product_data['images'])}")
           
            # Scrape detailed product information
            info_sections = self.driver.find_elements(By.CSS_SELECTOR,
                "div.flex.items-start.gap-3")
           
            for section in info_sections:
                try:
                    # Get the key (h3 element)
                    key_element = section.find_element(By.CSS_SELECTOR, "h3")
                    key = key_element.text.strip().lower()
                   
                    # Get the value (p element)
                    value_element = section.find_element(By.CSS_SELECTOR, "p")
                    value = value_element.text.strip()
                   
                    if key and value:
                        product_data['product_info'][key] = value
                       
                except NoSuchElementException:
                    continue
           
            print(f"Scraped {len(product_data['product_info'])} product details")
           
        except Exception as e:
            print(f"Error scraping product details: {e}")
       
        return product_data
   
    def scrape_all_products(self, search_query):
        """Main method to scrape all products for a search query"""
        # Get all product links
        product_links = self.search_products(search_query)
       
        if not product_links:
            print("No products found")
            return []
       
        # Scrape details for each product
        all_products_data = []
       
        for i, product in enumerate(product_links, 1):
            print(f"\nScraping product {i}/{len(product_links)}")
            try:
                product_data = self.scrape_product_details(
                    product['url'], product['out_of_stock'])
                all_products_data.append(product_data)
               
                # Add small delay between requests
                time.sleep(2)
               
            except Exception as e:
                print(f"Error scraping product {i}: {e}")
                continue
       
        self.products_data = all_products_data
        return all_products_data
   
    def save_to_excel(self, filename="zepto_products.xlsx"):
        """Save scraped data to Excel with separate columns"""
        if not self.products_data:
            print("No data to save")
            return
       
        # Prepare data for Excel
        excel_data = []
       
        for product in self.products_data:
            # Base product information
            row_data = {
                'Product URL': product.get('url', ''),
                'Out of Stock': product.get('out_of_stock', ''),
                'Product Name': product.get('product_name', ''),
                'Price': product.get('price', ''),
                'Pack Size': product.get('pack_size', ''),
                'Rating': product.get('rating', ''),
            }
           
            # Add all product info fields as separate columns
            for key, value in product.get('product_info', {}).items():
                row_data[key.title()] = value
           
            # Add image URLs (combine all images in one column)
            image_urls = []
            for img in product.get('images', []):
                image_urls.append(img.get('image_url', ''))
            row_data['Image URLs'] = ' | '.join(image_urls)
            row_data['Number of Images'] = len(product.get('images', []))
           
            excel_data.append(row_data)
       
        # Create DataFrame and save to Excel
        df = pd.DataFrame(excel_data)
       
        # Ensure directory exists for the Excel file
        target_dir = os.path.dirname(os.path.abspath(filename))
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # Save to Excel
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"\nData saved to {filename}")
        print(f"Total products scraped: {len(excel_data)}")
        print(f"Columns saved: {list(df.columns)}")
       
        return filename
   
    def download_images(self, download_folder="product_images", brand_override: str | None = None):
        """Download all product images organized by brand > product name.

        If brand_override is provided, use it as the brand folder name instead of
        inferring from the product details.
        """
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
       
        for i, product in enumerate(self.products_data):
            # Get brand name from product info or extract from product name
            brand_name = brand_override or product.get('product_info', {}).get('brand', 'Unknown_Brand')
            if brand_name == 'Unknown_Brand':
                # Try to extract brand from product name
                product_name = product.get('product_name', '')
                if product_name:
                    # Common brand extraction logic
                    for brand in ['Sunfeast', 'Parle', 'Britannia', 'ITC', 'Cadbury', 'Nestle']:
                        if brand.lower() in product_name.lower():
                            brand_name = brand
                            break
           
            # Clean brand name for folder
            safe_brand = "".join(c for c in brand_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_brand = safe_brand.replace(' ', '_')
           
            # Create product folder compatible with downstream: product_XXX_Title directly under download_folder
            product_name = product.get('product_name', f'product_{i+1}')
            safe_product_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
            product_folder = os.path.join(download_folder, f"product_{i+1:03d}_{safe_product_name}")
            if not os.path.exists(product_folder):
                os.makedirs(product_folder)
           
            print(f"Downloading images for: {brand_name} > {product_name}")
           
            for img_data in product.get('images', []):
                try:
                    img_url = img_data.get('image_url')
                    img_index = img_data.get('image_index', 0)
                   
                    if img_url:
                        response = requests.get(img_url, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        })
                        if response.status_code == 200:
                            # Extract file extension from URL or default to jpg
                            file_ext = 'jpg'
                            if '.' in img_url:
                                file_ext = img_url.split('.')[-1].split('?')[0]
                                if file_ext not in ['jpg', 'jpeg', 'png', 'webp']:
                                    file_ext = 'jpg'
                           
                            img_filename = f"image_{img_index + 1}.{file_ext}"
                            img_path = os.path.join(product_folder, img_filename)
                           
                            with open(img_path, 'wb') as f:
                                f.write(response.content)
                            print(f"  Downloaded: {img_filename}")
                       
                except Exception as e:
                    print(f"  Error downloading image {img_index}: {e}")
           
            # Write product_info.txt for downstream agents
            try:
                info_path = os.path.join(product_folder, "product_info.txt")
                with open(info_path, 'w', encoding='utf-8') as fh:
                    fh.write(f"Product Title: {product.get('product_name','')}\n")
                    fh.write(f"Product URL: {product.get('url','')}\n")
                    fh.write(f"Product Index: {i+1}\n")
                    fh.write(f"Scraped on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            except Exception:
                pass

            print(f"  Total images downloaded: {len(product.get('images', []))}")
   
    def close(self):
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")

def main():
    """Main function to run the scraper"""
    parser = argparse.ArgumentParser(description="Zepto product scraper")
    parser.add_argument("--brand", required=True, help="Brand name to search (use spaces, we will convert to '+')")
    parser.add_argument("--out-dir", default=os.path.join(os.getcwd(), "output"), help="Base folder to save Excel and images")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    brand_query = args.brand.strip()
    output_dir = os.path.abspath(args.out_dir)

    print(f"Brand provided: {brand_query}")
    print(f"Output directory: {output_dir}")

    # Initialize scraper
    scraper = ZeptoScraper(headless=args.headless)

    try:
        print(f"\n{'='*50}")
        print(f"Scraping products for brand: {brand_query}")
        print(f"Search URL will use query: {brand_query.replace(' ', '+')}")
        print(f"{'='*50}")

        # Scrape all products
        products = scraper.scrape_all_products(brand_query)

        # Save to Excel in the specified folder
        brand_underscore = brand_query.replace(' ', '_')
        excel_path = os.path.join(output_dir, f"zepto_{brand_underscore}_products.xlsx")
        scraper.save_to_excel(excel_path)

        # Download images into product_XXX_Title under output_dir
        print(f"\nDownloading images for {brand_query}...")
        scraper.download_images(download_folder=output_dir, brand_override=brand_query)

        # Create filtered_products.xlsx expected by downstream agents based on the Excel we saved
        try:
            df = pd.read_excel(excel_path)
            # Try to prepare a minimal file with 'title' and 'url'
            df_expected = pd.DataFrame()
            if 'Product Name' in df.columns:
                df_expected['title'] = df['Product Name']
            if 'Product URL' in df.columns:
                df_expected['url'] = df['Product URL']
            expected_path = os.path.join(output_dir, f"{brand_underscore}_filtered_products.xlsx")
            if not df_expected.empty and 'title' in df_expected.columns and 'url' in df_expected.columns:
                df_expected.to_excel(expected_path, index=False)
                print(f"Created downstream file: {expected_path}")
            else:
                print("Warning: Could not create filtered_products.xlsx due to missing columns")
        except Exception as e:
            print(f"Failed to create filtered_products.xlsx: {e}")

    except Exception as e:
        print(f"Error in main execution: {e}")
    finally:
        # Close browser
        scraper.close()

if __name__ == "__main__":
    main()
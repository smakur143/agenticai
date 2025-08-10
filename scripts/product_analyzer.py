import time
import os
import sys
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import requests
try:
    from textblob import TextBlob
    import nltk
    NLP_AVAILABLE = True
    # Download required NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')
except ImportError:
    NLP_AVAILABLE = False
    print("⚠️ TextBlob not available. Install with: pip install textblob nltk")
import re
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

# Configure UTF-8 encoding for console output (fixes Windows Unicode issues)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    # Python < 3.7 doesn't have reconfigure, try setting environment variable
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# Get parameters from command line
if len(sys.argv) < 4:
    print("Usage: python product_analyzer.py <scrape_site> <product_name> <output_folder>")
    sys.exit(1)

SCRAPE_SITE = sys.argv[1]
PRODUCT_NAME = sys.argv[2]
HOTFOLDER_PATH = sys.argv[3]

# Fix path handling - normalize and make absolute
if not os.path.isabs(HOTFOLDER_PATH):
    # If relative path, make it relative to current working directory
    HOTFOLDER_PATH = os.path.abspath(HOTFOLDER_PATH)
else:
    # If absolute path, normalize it
    HOTFOLDER_PATH = os.path.normpath(HOTFOLDER_PATH)

# Debug output to show paths being used
print(f"🔧 DEBUG: Script arguments received:")
print(f"   • Scrape Site: {SCRAPE_SITE}")
print(f"   • Product Name: {PRODUCT_NAME}")
print(f"   • Output Folder (Raw): {sys.argv[3]}")
print(f"   • Output Folder (Processed): {HOTFOLDER_PATH}")
print(f"   • Current Working Directory: {os.getcwd()}")

# Setup Chrome driver and image folder
OUTPUT_EXCEL_FILE = f"{PRODUCT_NAME.lower().replace(' ', '_')}_product_analysis.xlsx"
OUTPUT_EXCEL_PATH = os.path.join(HOTFOLDER_PATH, OUTPUT_EXCEL_FILE)

print(f"   • Excel File Name: {OUTPUT_EXCEL_FILE}")
print(f"   • Excel File Path: {OUTPUT_EXCEL_PATH}")
print(f"   • Does output directory exist: {os.path.exists(HOTFOLDER_PATH)}")
print("🔧 END DEBUG INFO\n")

# Try undetected_chromedriver first, fallback to regular selenium
driver = None
try:
    if UC_AVAILABLE:
        options = uc.ChromeOptions()
        options.headless = False
        options.add_argument('--start-maximized')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        try:
            driver = uc.Chrome(options=options, version_main=None)
            print("✅ Using undetected_chromedriver")
        except Exception as e:
            print(f"⚠️ Undetected_chromedriver failed: {e}")
            driver = None
    
    if driver is None:
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

def preprocess_text(text):
    """Preprocess text for sentiment analysis"""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace("isn't", "is not")
    text = text.replace("aren't", "are not")
    text = text.replace("doesn't", "does not")
    text = text.replace("don't", "do not")
    return text

def extract_product_rating(driver):
    """Extract product rating from the page"""
    try:
        rating_selectors = [
            "[data-hook='rating-out-of-text']",
            ".a-size-medium.a-color-base",
            "span[aria-hidden='true'] span.a-size-medium",
            ".cr-original-review-text"
        ]
        
        for selector in rating_selectors:
            try:
                rating_element = driver.find_element(By.CSS_SELECTOR, selector)
                rating_text = rating_element.text.strip()
                if "out of" in rating_text.lower():
                    return rating_text
            except:
                continue
        
        return "Rating not found"
    except Exception as e:
        return f"Error extracting rating: {str(e)}"

def extract_product_details(driver):
    """Extract product details table from the page"""
    try:
        details = {}
        
        # Try to find the product details table
        table_selectors = [
            "table.a-normal.a-spacing-micro",
            "table[role='list']",
            ".a-section .a-normal"
        ]
        
        table_found = False
        for selector in table_selectors:
            try:
                table = driver.find_element(By.CSS_SELECTOR, selector)
                rows = table.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            key = cells[0].text.strip()
                            value = cells[1].text.strip()
                            if key and value:
                                details[key] = value
                    except:
                        continue
                
                if details:
                    table_found = True
                    break
            except:
                continue
        
        if not table_found:
            # Try alternative method - look for specific detail elements
            detail_patterns = [
                ("Brand", ["po-brand", "brand"]),
                ("Variety", ["po-variety", "variety"]),
                ("Item Form", ["po-item_form", "item-form"]),
                ("Net Quantity", ["po-unit_count", "unit-count", "net-quantity"]),
                ("Diet Type", ["po-diet_type", "diet-type"])
            ]
            
            for detail_name, class_patterns in detail_patterns:
                for pattern in class_patterns:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, f".{pattern}")
                        for element in elements:
                            parent = element.find_element(By.XPATH, "..")
                            spans = parent.find_elements(By.TAG_NAME, "span")
                            if len(spans) >= 2:
                                details[detail_name] = spans[-1].text.strip()
                                break
                        if detail_name in details:
                            break
                    except:
                        continue
        
        return details if details else {"Details": "Not found"}
        
    except Exception as e:
        return {"Error": f"Error extracting details: {str(e)}"}

def analyze_itc_response_nlp(response_text):
    """Advanced NLP-based sentiment analysis to determine if product is ITC"""
    if not response_text or response_text == "No response found":
        return "No", 0.0, "No response available"
    
    if response_text.startswith("Error:"):
        return "No", 0.0, "Error in response"
    
    processed_text = preprocess_text(response_text)
    
    # Quick keyword-based checks for obvious cases (English)
    if any(phrase in processed_text for phrase in [
        "yes, this is an itc product", "yes, it is an itc product", 
        "manufactured by itc", "made by itc", "itc limited product"
    ]):
        return "Yes", 0.9, "Strong positive keyword match"
    
    # Quick keyword-based checks for obvious cases (Hindi)
    if any(phrase in processed_text for phrase in [
        "हाँ, यह आईटीसी का एक उत्पाद है", "यह आईटीसी का उत्पाद है", 
        "आईटीसी लिमिटेड द्वारा निर्मित", "आईटीसी द्वारा बनाया गया", 
        "आईटीसी का ब्रांड है", "आईटीसी कंपनी का उत्पाद"
    ]):
        return "Yes", 0.9, "Strong positive Hindi keyword match"
    
    if any(phrase in processed_text for phrase in [
        "no, this is not an itc product", "not an itc product", "not itc product", 
        "britannia product", "nestle product", "parle product"
    ]):
        return "No", -0.9, "Strong negative keyword match"
    
    # Hindi negative phrases
    if any(phrase in processed_text for phrase in [
        "नहीं, यह आईटीसी का उत्पाद नहीं है", "यह आईटीसी का उत्पाद नहीं है",
        "ब्रिटानिया का उत्पाद", "नेस्ले का उत्पाद", "पार्ले का उत्पाद"
    ]):
        return "No", -0.9, "Strong negative Hindi keyword match"
    
    if not NLP_AVAILABLE:
        # Enhanced keyword detection with Hindi support
        if any(phrase in processed_text for phrase in [
            "itc", "आईटीसी", "आइटिसी"
        ]) and any(phrase in processed_text for phrase in [
            "yes", "हाँ", "हा", "जी हाँ", "है"
        ]):
            return "Yes", 0.5, "Simple keyword fallback - positive"
        elif any(phrase in processed_text for phrase in [
            "no", "नहीं", "नही", "नै"
        ]) or any(brand in processed_text for brand in [
            "britannia", "nestle", "parle", "cadbury", "unilever", 
            "ब्रिटानिया", "नेस्ले", "पार्ले", "कैडबरी"
        ]):
            return "No", -0.5, "Simple keyword fallback - negative"
        else:
            return "No", 0.0, "Simple keyword fallback - unclear"
    
    # Advanced NLP analysis
    try:
        blob = TextBlob(processed_text)
        sentiment_score = blob.sentiment.polarity
        
        sentences = blob.sentences
        itc_sentiment = 0.0
        itc_mentions = 0
        
        for sentence in sentences:
            sentence_text = str(sentence).lower()
            if "itc" in sentence_text:
                itc_mentions += 1
                sentence_sentiment = sentence.sentiment.polarity
                
                if any(pos_word in sentence_text for pos_word in [
                    "yes", "is", "manufactured", "made", "product", "brand"
                ]):
                    itc_sentiment += sentence_sentiment * 1.5
                elif any(neg_word in sentence_text for neg_word in [
                    "no", "not", "isn't", "aren't"
                ]):
                    itc_sentiment += sentence_sentiment * -1.5
                else:
                    itc_sentiment += sentence_sentiment
        
        if itc_mentions > 0:
            final_score = itc_sentiment / itc_mentions
        else:
            final_score = sentiment_score
        
        yes_pattern = re.search(r'\byes\b.*\bitc\b', processed_text)
        no_pattern = re.search(r'\bno\b.*\bitc\b', processed_text)
        
        if yes_pattern and not no_pattern:
            final_score = max(final_score, 0.6)
        elif no_pattern and not yes_pattern:
            final_score = min(final_score, -0.6)
        
        competitor_brands = [
            "britannia", "nestle", "parle", "cadbury", "unilever", 
            "hindustan unilever", "dabur", "marico", "godrej", 
            "tata", "patanjali", "amul", "mother dairy",
            "ब्रिटानिया", "नेस्ले", "पार्ले", "कैडबरी", "यूनिलीवर",
            "हिंदुस्तान यूनिलीवर", "डाबर", "मैरिको", "गोदरेज",
            "टाटा", "पतंजलि", "अमूल"
        ]
        
        # Check for ITC-related Hindi terms
        itc_hindi_terms = ["आईटीसी", "आइटिसी", "आई टी सी"]
        itc_hindi_mentioned = any(term in processed_text for term in itc_hindi_terms)
        if itc_hindi_mentioned:
            final_score = max(final_score, 0.4)
        
        competitor_mentioned = any(brand in processed_text for brand in competitor_brands)
        if competitor_mentioned:
            final_score = min(final_score, -0.3)
        
        if final_score > 0.3:
            result = "Yes"
            explanation = f"Positive sentiment towards ITC (score: {final_score:.2f})"
        elif final_score < -0.2:
            result = "No"
            explanation = f"Negative sentiment towards ITC (score: {final_score:.2f})"
        else:
            result = "No"
            explanation = f"Neutral/unclear sentiment (score: {final_score:.2f})"
        
        return result, final_score, explanation
        
    except Exception as e:
        print(f"❌ NLP analysis failed: {e}")
        if "yes" in processed_text and "itc" in processed_text:
            return "Yes", 0.5, "NLP fallback - positive"
        else:
            return "No", -0.5, "NLP fallback - negative"

def check_itc_product(url, product_title):
    """Visit a product URL and check if it's an ITC product using Amazon's search feature"""
    try:
        print(f"🔍 Checking: {product_title}")
        driver.get(url)
        time.sleep(3)

        # Extract product rating
        rating = extract_product_rating(driver)
        print(f"⭐ Rating: {rating}")

        # Extract product details
        details = extract_product_details(driver)
        print(f"📋 Details extracted: {len(details)} items")

        # Click on "Search this page" link
        search_input_found = False
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                search_link = driver.find_element(By.ID, "askATFLink")
                search_link.click()
                print(f"✅ Clicked 'Search this page' (attempt {attempt + 1})")
                time.sleep(2)
                
                # Find and fill the search input
                try:
                    search_input = driver.find_element(By.ID, "dpx-rex-nile-search-text-input")
                    search_input.clear()
                    search_input.send_keys("Is it ITC product?")
                    print("✅ Entered search query")
                    time.sleep(1)
                    search_input_found = True
                    break
                except Exception as e:
                    print(f"❌ Failed to find search input (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        print("🔄 Retrying...")
                        time.sleep(3)
                        continue
                    
            except Exception as e:
                print(f"❌ Failed to find 'Search this page' link (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print("🔄 Retrying...")
                    time.sleep(3)
                    continue

        if not search_input_found:
            return "Not Verified", rating, details

        # Click submit button
        try:
            submit_button = driver.find_element(By.ID, "dpx-rex-nile-submit-button-announce")
            submit_button.click()
            print("✅ Clicked submit button")
        except Exception as e:
            print(f"❌ Failed to find submit button: {e}")
            return "Not Verified", rating, details

        # Wait for response (10 seconds)
        print("⏳ Waiting for response...")
        time.sleep(10)

        # Try to find the response
        response_selectors = [
            "div[data-ask-blue-chunk-type='inference']",
            "div[aria-live='polite']",
            "div.text-subsection-spacing",
            "div[id*='section_groupId_text_template']",
            ".a-section.a-spacing-none"
        ]

        response_text = "No response found"
        for selector in response_selectors:
            try:
                response_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in response_elements:
                    text = element.text.strip()
                    if text and len(text) > 10:
                        response_text = text
                        print(f"✅ Found response: {response_text[:100]}...")
                        break
                if response_text != "No response found":
                    break
            except:
                continue

        return response_text, rating, details

    except Exception as e:
        print(f"❌ Error checking product: {e}")
        return f"Error: {str(e)}", "Rating not available", {"Error": str(e)}

def scrape_products_from_current_page(driver):
    """Scrape all product links from the current search results page"""
    print("📜 Scrolling to load all products on current page...")
    
    # Scroll multiple times to load all products
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0
    max_scroll_attempts = 10
    
    while scroll_attempts < max_scroll_attempts:
        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Check if new content loaded
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scroll_attempts += 1
        print(f"Scrolled {scroll_attempts}/{max_scroll_attempts} times")
    
    print("✅ Finished scrolling, now extracting product links...")
    
    # Extract product links from the current page
    product_links = []
    product_titles = []
    
    # Try to find the search results container first
    try:
        search_results_container = driver.find_element(By.CSS_SELECTOR, "[data-component-type='s-search-results']")
        print("✅ Found s-search-results container")
    except:
        print("⚠️ Could not find s-search-results container, using document body")
        search_results_container = driver.find_element(By.TAG_NAME, "body")
    
    # Multiple selectors to try for product links
    product_selectors = [
        # Main product link selectors
        "div[data-component-type='s-search-result'] h2 a",
        "div.s-result-item h2 a", 
        "div[data-asin] h2 a",
        "a.a-link-normal.s-line-clamp-3",
        "a.a-link-normal.s-link-style.a-text-normal",
        "h3.s-size-mini a",
        "h2.s-size-mini a",
        # Additional selectors
        "div.s-result-item a[href*='/dp/']",
        "div[data-asin] a[href*='/dp/']",
        "a[href*='/dp/'][data-component-type!='s-product-image']"  # Exclude image links
    ]
    
    for selector in product_selectors:
        try:
            link_elements = search_results_container.find_elements(By.CSS_SELECTOR, selector)
            if link_elements:
                print(f"✅ Found {len(link_elements)} links with selector: {selector}")
                
                for link in link_elements:
                    try:
                        href = link.get_attribute("href")
                        if href and ("/dp/" in href or "/gp/product/" in href):
                            # Clean up the URL - remove tracking parameters for cleaner URLs
                            if "/dp/" in href:
                                clean_href = href.split("/dp/")[0] + "/dp/" + href.split("/dp/")[1].split("/")[0]
                            elif "/gp/product/" in href:
                                clean_href = href.split("/gp/product/")[0] + "/gp/product/" + href.split("/gp/product/")[1].split("/")[0]
                            else:
                                clean_href = href
                            
                            # Get title from various sources
                            title = (link.get_attribute("aria-label") or 
                                   link.text or 
                                   link.get_attribute("title") or 
                                   "No title")
                            
                            # Remove "Sponsored Ad -" prefix if present
                            if title.startswith("Sponsored Ad - "):
                                title = title[15:]
                            
                            title = title.strip()
                            
                            # Avoid duplicates
                            if clean_href not in product_links and title != "No title":
                                product_links.append(clean_href)
                                product_titles.append(title)
                    except Exception as e:
                        continue
                
                if len(product_links) > 0:
                    break  # Found products with this selector, no need to try others
        except Exception as e:
            continue
    
    print(f"📦 Extracted {len(product_links)} unique product links from current page")
    return product_links, product_titles

def check_and_navigate_to_next_page(driver):
    """Check if there's a next page and navigate to it"""
    try:
        # Look for the "Next" pagination button
        next_button_selectors = [
            "a.s-pagination-next",
            "a[aria-label*='next page']",
            "a[aria-label*='Next']",
            "li.a-last a",
            "span.s-pagination-item.s-pagination-next a"
        ]
        
        next_button = None
        for selector in next_button_selectors:
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, selector)
                if next_button.is_enabled() and next_button.is_displayed():
                    print(f"✅ Found next button with selector: {selector}")
                    break
            except:
                continue
        
        if next_button:
            # Scroll to the pagination area
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(1)
            
            # Click the next button
            driver.execute_script("arguments[0].click();", next_button)
            print("✅ Clicked next page button")
            time.sleep(5)  # Wait for page to load
            return True
        else:
            print("📄 No more pages available")
            return False
            
    except Exception as e:
        print(f"❌ Error navigating to next page: {e}")
        return False

def collect_all_products_across_pages(driver, max_pages=10):
    """Collect all product links across multiple pages"""
    all_product_links = []
    all_product_titles = []
    current_page = 1
    
    print(f"\n🔍 Starting product collection across multiple pages (max: {max_pages})...")
    
    while current_page <= max_pages:
        print(f"\n📄 Processing page {current_page}...")
        
        # Wait for page to load completely
        time.sleep(3)
        
        # Scrape products from current page
        page_links, page_titles = scrape_products_from_current_page(driver)
        
        # Add to master lists
        all_product_links.extend(page_links)
        all_product_titles.extend(page_titles)
        
        print(f"📊 Page {current_page}: Found {len(page_links)} products")
        print(f"📊 Total so far: {len(all_product_links)} products")
        
        # Try to navigate to next page
        if current_page < max_pages:
            has_next_page = check_and_navigate_to_next_page(driver)
            if not has_next_page:
                print(f"🏁 Reached end of results at page {current_page}")
                break
        
        current_page += 1
    
    print(f"\n🎉 Completed product collection!")
    print(f"📊 Total products collected: {len(all_product_links)} across {current_page} pages")
    
    return all_product_links, all_product_titles

def apply_brand_filters(driver, product_name):
    """Apply brand filters automatically based on the product name"""
    try:
        print(f"\n🔍 Looking for brand filters related to '{product_name}'...")
        
        # Wait for filters to load
        time.sleep(3)
        
        # Look for the filters panel/section
        filter_selectors = [
            "[data-component-type='s-filters-panel-view']",
            ".s-widget-container.s-spacing-medium.s-widget-container-height-medium",
            "#s-refinements",
            ".a-section.a-spacing-none"
        ]
        
        filters_panel = None
        for selector in filter_selectors:
            try:
                filters_panel = driver.find_element(By.CSS_SELECTOR, selector)
                print(f"✅ Found filters panel with selector: {selector}")
                break
            except:
                continue
        
        if not filters_panel:
            print("⚠️ Could not find filters panel")
            return False
        
        # Look for brand section in filters
        brand_section_selectors = [
            "div[data-csa-c-content-id*='brand']",
            "div[data-csa-c-content-id*='Brand']",
            "div[data-csa-c-content-id*='BRAND']",
            ".s-navigation-item:has(span:contains('Brand'))",
            "div:has(> span:contains('Brand'))",
            "div:has(> span:contains('brand'))"
        ]
        
        brand_section = None
        for selector in brand_section_selectors:
            try:
                brand_elements = filters_panel.find_elements(By.CSS_SELECTOR, selector)
                for element in brand_elements:
                    if "brand" in element.text.lower():
                        brand_section = element
                        print(f"✅ Found brand section with selector: {selector}")
                        break
                if brand_section:
                    break
            except:
                continue
        
        if not brand_section:
            print("⚠️ Could not find brand section in filters")
            return False
        
        # Find all brand checkboxes or links
        brand_options = []
        brand_selectors = [
            "span.a-list-item input[type='checkbox']",
            "span.a-list-item a",
            "li input[type='checkbox']",
            "li a[href*='rh=']"
        ]
        
        for selector in brand_selectors:
            try:
                elements = brand_section.find_elements(By.CSS_SELECTOR, selector)
                brand_options.extend(elements)
            except:
                continue
        
        print(f"📊 Found {len(brand_options)} brand filter options")
        
        # Find matching brands
        product_name_lower = product_name.lower()
        matching_brands = []
        
        for option in brand_options:
            try:
                # Get the brand name from different sources
                brand_text = ""
                if option.tag_name == "input":
                    # For checkboxes, look for nearby text
                    parent = option.find_element(By.XPATH, "..")
                    brand_text = parent.text.strip()
                elif option.tag_name == "a":
                    # For links, get the text content
                    brand_text = option.text.strip()
                
                if brand_text and product_name_lower in brand_text.lower():
                    matching_brands.append((option, brand_text))
                    print(f"🎯 Found matching brand: {brand_text}")
            except:
                continue
        
        # Apply filters for matching brands
        applied_filters = 0
        for option, brand_text in matching_brands:
            try:
                # Scroll the element into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option)
                time.sleep(0.5)
                
                # Click the filter option
                if option.tag_name == "input" and not option.is_selected():
                    driver.execute_script("arguments[0].click();", option)
                    applied_filters += 1
                    print(f"✅ Applied filter for brand: {brand_text}")
                elif option.tag_name == "a":
                    driver.execute_script("arguments[0].click();", option)
                    applied_filters += 1
                    print(f"✅ Applied filter for brand: {brand_text}")
                    break  # For links, we typically only click one
                
                time.sleep(1)  # Wait between filter applications
            except Exception as e:
                print(f"❌ Failed to apply filter for {brand_text}: {e}")
        
        if applied_filters > 0:
            print(f"🎉 Successfully applied {applied_filters} brand filters")
            time.sleep(3)  # Wait for page to update
            return True
        else:
            print("⚠️ No brand filters were applied")
            return False
            
    except Exception as e:
        print(f"❌ Error applying brand filters: {e}")
        return False

def main():
    try:
        # Use local variables to avoid global declaration issues
        output_folder = HOTFOLDER_PATH
        excel_path = OUTPUT_EXCEL_PATH
        
        # Ensure the output folder path exists and is properly formatted
        print(f"📁 Processing output folder path...")
        print(f"   • Raw input path: {sys.argv[3]}")
        print(f"   • Processed path: {output_folder}")
        print(f"   • Current working directory: {os.getcwd()}")
        
        # Create the output directory with proper error handling
        try:
            os.makedirs(output_folder, exist_ok=True)
            print(f"✅ Output folder created/verified: {output_folder}")
            
            # Verify the directory was actually created
            if not os.path.exists(output_folder):
                raise Exception(f"Failed to create directory: {output_folder}")
            
            # Test write permissions
            test_file = os.path.join(output_folder, "test_write.tmp")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print(f"✅ Write permissions verified for: {output_folder}")
            except Exception as e:
                raise Exception(f"No write permissions for directory {output_folder}: {e}")
                
        except Exception as e:
            print(f"❌ Error creating output folder: {e}")
            # Fallback to current directory
            fallback_path = os.path.join(os.getcwd(), "output")
            print(f"⚠️ Using fallback directory: {fallback_path}")
            os.makedirs(fallback_path, exist_ok=True)
            # Update the local path variables
            output_folder = fallback_path
            excel_path = os.path.join(output_folder, OUTPUT_EXCEL_FILE)
            print(f"✅ Updated Excel path: {excel_path}")
        
        print("🔐 Logging into Amazon...")
        # Login to Amazon
        driver.get("https://www.amazon.in")
        time.sleep(5)

        # Handle popups
        try:
            continue_btn = driver.find_element(By.XPATH, '//button[@class="a-button-text" and @type="submit"]')
            continue_btn.click()
            print("✅ Clicked 'Continue shopping'")
            time.sleep(3)
        except:
            print("'Continue shopping' not found — skipping...")

        # Amazon login process
        try:
            driver.find_element(By.ID, "nav-link-accountList").click()
            time.sleep(3)
            print("✅ Clicked sign in")
        except Exception as e:
            print(f"❌ Failed to click sign in: {e}")

        try:
            email_input = driver.find_element(By.ID, "ap_email_login")
            email_input.send_keys("souvagyad6@gmail.com")
            driver.find_element(By.ID, "continue").click()
            time.sleep(3)
            print("✅ Entered email")
        except Exception as e:
            print(f"❌ Failed to enter email: {e}")

        try:
            time.sleep(2)
            password_input = None
            selectors_to_try = ["ap_password", "password", "signInPassword", "auth-password-input"]
            
            for selector in selectors_to_try:
                try:
                    password_input = driver.find_element(By.ID, selector)
                    print(f"✅ Found password field with ID: {selector}")
                    break
                except:
                    continue
            
            if password_input is None:
                try:
                    password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                    print("✅ Found password field by type")
                except:
                    print("❌ Could not find password field")
                    raise Exception("Password field not found")
            
            password_input.send_keys("P@ssw0rd")  # Replace with your password
            
            submit_selectors = ["signInSubmit", "auth-signin-button", "continue"]
            submit_clicked = False
            
            for submit_id in submit_selectors:
                try:
                    driver.find_element(By.ID, submit_id).click()
                    print(f"✅ Clicked submit button: {submit_id}")
                    submit_clicked = True
                    break
                except:
                    continue
            
            if not submit_clicked:
                try:
                    driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
                    print("✅ Clicked submit button by type")
                except:
                    print("❌ Could not find submit button")
            
            time.sleep(5)
            print("✅ Login attempt completed")
            
        except Exception as e:
            print(f"❌ Login failed: {e}")
            print("Continuing without login")

        # Search for products
        print(f"\n🔍 Searching for {PRODUCT_NAME} products...")
        try:
            search_box = driver.find_element(By.ID, "twotabsearchtextbox")
            search_box.clear()
            search_box.send_keys(PRODUCT_NAME)
            search_box.send_keys(Keys.RETURN)
            print(f"✅ Search executed successfully for {PRODUCT_NAME}")
            time.sleep(5)
        except Exception as e:
            print(f"❌ Failed to search: {e}")
            return

        print(f"Current URL: {driver.current_url}")

        # Apply brand filters if applicable
        if apply_brand_filters(driver, PRODUCT_NAME):
            print(f"🎉 Applied brand filters for '{PRODUCT_NAME}'.")
            time.sleep(5) # Wait for filters to apply and page to update
        else:
            print(f"⚠️ Could not apply brand filters for '{PRODUCT_NAME}'. Proceeding without filters.")

        # Collect all products across multiple pages
        product_links, product_titles = collect_all_products_across_pages(driver, max_pages=5)

        if not product_links:
            print("❌ No product links found to process")
            return

        # Create initial dataframe with all scraped products
        df = pd.DataFrame({
            'title': product_titles,
            'url': product_links,
            'rating': "",
            'brand': "",
            'variety': "",
            'item_form': "",
            'net_quantity': "",
            'diet_type': "",
            'other_details': "",
            'Is it ITC product?': "",
            'ITC Product (Yes/No)': ""
        })

        print(f"\n📊 Initial dataset: {len(df)} products collected")
        
        # Filter products based on brand name in title
        print(f"\n🔍 Filtering products that contain '{PRODUCT_NAME}' in title...")
        
        # Sort by title first
        df = df.sort_values('title', ascending=True).reset_index(drop=True)
        print(f"✅ Sorted {len(df)} products by title")
        
        # Filter to keep only products with brand name in title
        brand_name_lower = PRODUCT_NAME.lower()
        mask = df['title'].str.lower().str.contains(brand_name_lower, na=False)
        filtered_df = df[mask].reset_index(drop=True)
        
        removed_count = len(df) - len(filtered_df)
        print(f"📋 Filtering results:")
        print(f"   • Products containing '{PRODUCT_NAME}': {len(filtered_df)}")
        print(f"   • Products removed: {removed_count}")
        print(f"   • Retention rate: {(len(filtered_df)/len(df)*100):.1f}%")
        
        if len(filtered_df) == 0:
            print(f"❌ No products found containing '{PRODUCT_NAME}' in title")
            print("💡 Suggestion: Try a broader search term or check spelling")
            return
        
        # Use the filtered dataframe for further processing
        df = filtered_df
        
        # Save the filtered list before ITC analysis
        try:
            filtered_excel_path = os.path.join(output_folder, f"{PRODUCT_NAME.lower().replace(' ', '_')}_filtered_products.xlsx")
            df.to_excel(filtered_excel_path, index=False)
            print(f"💾 Saved filtered product list to: {filtered_excel_path}")
        except Exception as e:
            print(f"⚠️ Could not save filtered list: {e}")

        print(f"\n🔍 Starting ITC analysis on {len(df)} filtered products...")
        for idx, row in df.iterrows():
            product_url = row['url']
            product_title = row['title']
            
            print(f"\n🛒 Processing product {idx+1}/{len(df)}: {product_title}")
            
            # Check if it's an ITC product and extract additional details
            result, rating, details = check_itc_product(product_url, product_title)
            df.at[idx, 'Is it ITC product?'] = result
            df.at[idx, 'rating'] = rating
            
            # Extract specific details from the details dictionary
            df.at[idx, 'brand'] = details.get('Brand', '')
            df.at[idx, 'variety'] = details.get('Variety', '')
            df.at[idx, 'item_form'] = details.get('Item Form', '')
            df.at[idx, 'net_quantity'] = details.get('Net Quantity', '')
            df.at[idx, 'diet_type'] = details.get('Diet Type', '')
            
            # Store any other details as JSON string
            other_details = {k: v for k, v in details.items() 
                           if k not in ['Brand', 'Variety', 'Item Form', 'Net Quantity', 'Diet Type']}
            df.at[idx, 'other_details'] = str(other_details) if other_details else ""
            
            # Perform NLP sentiment analysis only if result is not "Not Verified"
            if result != "Not Verified":
                sentiment_result, sentiment_score, explanation = analyze_itc_response_nlp(result)
                df.at[idx, 'ITC Product (Yes/No)'] = sentiment_result
                
                print(f"📊 NLP Analysis: {sentiment_result} (Score: {sentiment_score:.2f})")
                print(f"💭 Explanation: {explanation}")
            else:
                df.at[idx, 'ITC Product (Yes/No)'] = "Not Verified"
                print(f"❓ Product verification failed - marked as Not Verified")
            
            # Save progress with enhanced error handling
            try:
                print(f"💾 Saving progress to: {excel_path}")
                # Ensure directory still exists before saving
                if not os.path.exists(output_folder):
                    os.makedirs(output_folder, exist_ok=True)
                    print(f"📁 Recreated output directory: {output_folder}")
                
                df.to_excel(excel_path, index=False)
                
                # Verify file was actually saved
                if os.path.exists(excel_path):
                    file_size = os.path.getsize(excel_path)
                    print(f"✅ Progress saved successfully ({file_size} bytes)")
                else:
                    print(f"❌ File was not saved to expected location: {excel_path}")
                    
            except Exception as save_error:
                print(f"❌ Error saving progress: {save_error}")
                # Try saving to current directory as backup
                backup_path = os.path.join(os.getcwd(), OUTPUT_EXCEL_FILE)
                try:
                    df.to_excel(backup_path, index=False)
                    print(f"⚠️ Saved to backup location: {backup_path}")
                except:
                    print(f"❌ Failed to save backup file as well")
            
            time.sleep(2)

        # Final summary
        yes_count = (df['ITC Product (Yes/No)'] == 'Yes').sum()
        no_count = (df['ITC Product (Yes/No)'] == 'No').sum()
        not_verified_count = (df['ITC Product (Yes/No)'] == 'Not Verified').sum()
        
        print(f"\n🎉 Completed product analysis!")
        print(f"📊 Summary: {yes_count} ITC products, {no_count} non-ITC products, {not_verified_count} not verified")
        if NLP_AVAILABLE:
            print(f"🧠 Used advanced NLP sentiment analysis with Hindi language support")
        print(f"⭐ Extracted product ratings and detailed specifications")
        print(f"📁 Results saved to: {OUTPUT_EXCEL_FILE}")
        print(f"📂 Location: {output_folder}")
        print(f"📄 Full Excel path: {excel_path}")
        
        # Final verification of saved file
        if os.path.exists(excel_path):
            final_size = os.path.getsize(excel_path)
            print(f"✅ Final file confirmed: {final_size} bytes at {excel_path}")
        else:
            print(f"❌ WARNING: Final file not found at expected location!")

    except Exception as e:
        print(f"❌ Error in main process: {e}")
    
    finally:
        if driver:
            driver.quit()
        print("🔄 Browser closed")

if __name__ == '__main__':
    main() 
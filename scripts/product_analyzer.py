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

# Debug output to show paths being used
print(f"🔧 DEBUG: Script arguments received:")
print(f"   • Scrape Site: {SCRAPE_SITE}")
print(f"   • Product Name: {PRODUCT_NAME}")
print(f"   • Output Folder (Raw): {HOTFOLDER_PATH}")
print(f"   • Output Folder (Absolute): {os.path.abspath(HOTFOLDER_PATH)}")
print(f"   • Current Working Directory: {os.getcwd()}")

# Setup Chrome driver and image folder
OUTPUT_EXCEL_FILE = f"{PRODUCT_NAME.lower().replace(' ', '_')}_product_analysis.xlsx"
OUTPUT_EXCEL_PATH = os.path.join(HOTFOLDER_PATH, OUTPUT_EXCEL_FILE)

print(f"   • Excel File Name: {OUTPUT_EXCEL_FILE}")
print(f"   • Excel File Path: {OUTPUT_EXCEL_PATH}")
print(f"   • Excel File Path (Absolute): {os.path.abspath(OUTPUT_EXCEL_PATH)}")
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

def main():
    try:
        print(f"📁 Creating output folder: {HOTFOLDER_PATH}")
        print(f"📁 Absolute path: {os.path.abspath(HOTFOLDER_PATH)}")
        os.makedirs(HOTFOLDER_PATH, exist_ok=True)
        print(f"✅ Output folder created/verified: {HOTFOLDER_PATH}")
        
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

        # Scroll to load more products
        print("📜 Scrolling to load more products...")
        for i in range(5):
            driver.execute_script("window.scrollBy(0, 1000);")
            print(f"Scrolled {i+1}/5")
            time.sleep(2)

        time.sleep(3)
        print(f"Current URL: {driver.current_url}")

        # Extract product links
        product_links = []
        product_titles = []
        
        selectors_to_try = [
            "a.a-link-normal.s-line-clamp-3.s-link-style.a-text-normal",
            "a.a-link-normal.s-link-style.a-text-normal",
            "a[data-component-type='s-search-result']",
            "h3.s-size-mini a",
            "h2.s-size-mini a"
        ]
        
        for selector in selectors_to_try:
            try:
                link_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if link_elements:
                    print(f"✅ Found {len(link_elements)} links with selector: {selector}")
                    break
            except:
                continue
        else:
            print("❌ No product links found")
            return
        
        for link in link_elements:
            href = link.get_attribute("href")
            title = link.get_attribute("aria-label") or link.text or "No title"
            if href and "/dp/" in href:
                product_links.append(href)
                product_titles.append(title.strip())
        
        print(f"Found {len(product_links)} valid product links")

        if not product_links:
            print("❌ No product links found to process")
            return

        # Create dataframe and check each product for ITC
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

        print(f"\n🔍 Checking each product for ITC affiliation...")
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
            
            # Save progress
            df.to_excel(OUTPUT_EXCEL_PATH, index=False)
            print(f"💾 Saved progress to Excel")
            
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
        print(f"📂 Location: {HOTFOLDER_PATH}")
        print(f"📂 Absolute location: {os.path.abspath(HOTFOLDER_PATH)}")
        print(f"📄 Full Excel path: {os.path.abspath(OUTPUT_EXCEL_PATH)}")

    except Exception as e:
        print(f"❌ Error in main process: {e}")
    
    finally:
        if driver:
            driver.quit()
        print("🔄 Browser closed")

if __name__ == '__main__':
    main() 
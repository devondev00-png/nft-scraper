"""
Selenium-based scraper for NFT marketplaces as fallback
Scrapes OpenSea, Magic Eden, etc. when APIs are unavailable
"""

import asyncio
from typing import Dict, Any, Optional
from loguru import logger

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not available - install with: pip install selenium")


class SeleniumScraper:
    """Selenium-based scraper for NFT marketplace pages"""
    
    def __init__(self, headless: bool = True):
        """Initialize Selenium scraper"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is not installed")
        self.headless = headless
        self.driver = None
    
    def _get_driver(self):
        """Get or create WebDriver instance"""
        if self.driver is None:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
            except (WebDriverException, Exception) as e:
                # Try Firefox as fallback
                try:
                    from selenium.webdriver.firefox.options import Options as FirefoxOptions
                    firefox_options = FirefoxOptions()
                    if self.headless:
                        firefox_options.add_argument("--headless")
                    self.driver = webdriver.Firefox(options=firefox_options)
                except (WebDriverException, Exception):
                    logger.debug(f"Could not initialize WebDriver: {e}. Selenium scraping disabled.")
                    # Don't raise - just disable Selenium
                    return None
        return self.driver
    
    async def get_collection_info_from_url(self, url: str) -> Dict[str, Any]:
        """
        Scrape collection info from marketplace URL
        
        Args:
            url: Collection URL (OpenSea, Magic Eden, etc.)
        
        Returns:
            Dict with collection information
        """
        if not SELENIUM_AVAILABLE:
            return {}
        
        try:
            # Add timeout to prevent hanging
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._scrape_url, url),
                timeout=10.0  # 10 second timeout
            )
        except asyncio.TimeoutError:
            logger.debug(f"Selenium scraping timeout for {url}")
            return {}
        except Exception as e:
            logger.debug(f"Selenium scraping error for {url}: {e}")
            return {}
    
    def _scrape_url(self, url: str) -> Dict[str, Any]:
        """Synchronous scraping method"""
        driver = self._get_driver()
        if not driver:
            return {}  # Driver not available, skip scraping
        
        result = {}
        
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait a bit for dynamic content to load
            import time
            time.sleep(3)
            
            # Try to extract collection info based on marketplace
            url_lower = url.lower()
            
            if "opensea.io" in url_lower:
                result = self._scrape_opensea(driver)
            elif "magiceden" in url_lower:
                result = self._scrape_magiceden(driver)
            elif "solanart" in url_lower:
                result = self._scrape_solanart(driver)
            else:
                # Generic scraping
                result = self._scrape_generic(driver)
                
        except TimeoutException:
            logger.debug(f"Selenium timeout for {url}")
        except Exception as e:
            logger.debug(f"Selenium scraping error for {url}: {e}")
        finally:
            # Don't close driver - reuse it
            pass
        
        return result
    
    def _scrape_opensea(self, driver) -> Dict[str, Any]:
        """Scrape OpenSea collection page"""
        result = {}
        try:
            # Collection name
            try:
                name_elem = driver.find_element(By.CSS_SELECTOR, "h1[style*='font'], h1.collection-name, .AssetHeader--name")
                result["name"] = name_elem.text.strip()
            except Exception:
                # Element not found, continue
                pass
            
            # Description
            try:
                desc_elem = driver.find_element(By.CSS_SELECTOR, ".CollectionDescription, .AssetHeader--description, [data-testid='collection-description']")
                result["description"] = desc_elem.text.strip()
            except Exception:
                # Element not found, continue
                pass
            
            # Floor price
            try:
                floor_elem = driver.find_element(By.CSS_SELECTOR, "[data-testid='floor-price'], .AssetHeader--collection-floor-price, .Price--amount")
                floor_text = floor_elem.text.strip()
                # Extract number
                import re
                match = re.search(r'([\d,]+\.?\d*)', floor_text.replace(',', ''))
                if match:
                    result["floor_price"] = float(match.group(1))
            except Exception:
                # Element not found or parsing failed, continue
                pass
            
            # Total supply / items
            try:
                supply_elem = driver.find_element(By.CSS_SELECTOR, "[data-testid='collection-total-supply'], .CollectionStats--items, .CollectionStats--supply")
                supply_text = supply_elem.text.strip()
                import re
                match = re.search(r'([\d,]+)', supply_text.replace(',', ''))
                if match:
                    result["total_supply"] = int(match.group(1))
            except Exception:
                # Element not found or parsing failed, continue
                pass
            
            # Volume
            try:
                volume_elems = driver.find_elements(By.CSS_SELECTOR, "[data-testid*='volume'], .CollectionStats--volume")
                for vol_elem in volume_elems:
                    vol_text = vol_elem.text.strip().lower()
                    if 'total' in vol_text or 'all' in vol_text:
                        import re
                        match = re.search(r'([\d,]+\.?\d*)', vol_text.replace(',', ''))
                        if match:
                            result["total_volume"] = float(match.group(1))
            except Exception:
                # Element not found or parsing failed, continue
                pass
            
            # Owners
            try:
                owners_elem = driver.find_element(By.CSS_SELECTOR, "[data-testid*='owner'], .CollectionStats--owners")
                owners_text = owners_elem.text.strip()
                import re
                match = re.search(r'([\d,]+)', owners_text.replace(',', ''))
                if match:
                    result["total_owners"] = int(match.group(1))
            except Exception:
                # Element not found or parsing failed, continue
                pass
            
            # Image
            try:
                img_elem = driver.find_element(By.CSS_SELECTOR, ".AssetHeader--img, .CollectionHeader--image img, [data-testid='collection-image'] img")
                result["image_url"] = img_elem.get_attribute("src")
            except Exception:
                # Element not found, continue
                pass
            
        except Exception as e:
            logger.debug(f"OpenSea scraping error: {e}")
        
        return result
    
    def _scrape_magiceden(self, driver) -> Dict[str, Any]:
        """Scrape Magic Eden collection page"""
        result = {}
        try:
            # Collection name
            try:
                name_elem = driver.find_element(By.CSS_SELECTOR, "h1, .collection-name, [data-testid='collection-name']")
                result["name"] = name_elem.text.strip()
            except Exception:
                # Element not found, continue
                pass
            
            # Description
            try:
                desc_elem = driver.find_element(By.CSS_SELECTOR, ".collection-description, [data-testid='collection-description']")
                result["description"] = desc_elem.text.strip()
            except Exception:
                # Element not found, continue
                pass
            
            # Floor price
            try:
                floor_elem = driver.find_element(By.CSS_SELECTOR, "[data-testid='floor-price'], .floor-price, .stats-floor")
                floor_text = floor_elem.text.strip()
                import re
                match = re.search(r'([\d,]+\.?\d*)', floor_text.replace(',', '').replace(' SOL', ''))
                if match:
                    result["floor_price"] = float(match.group(1))
                    result["floor_price_currency"] = "SOL"
            except Exception:
                # Element not found or parsing failed, continue
                pass
            
            # Total items
            try:
                items_elem = driver.find_element(By.CSS_SELECTOR, "[data-testid='collection-items'], .items-count, .collection-stats-items")
                items_text = items_elem.text.strip()
                import re
                match = re.search(r'([\d,]+)', items_text.replace(',', ''))
                if match:
                    result["total_supply"] = int(match.group(1))
            except Exception:
                # Element not found or parsing failed, continue
                pass
            
            # Volume
            try:
                volume_elems = driver.find_elements(By.CSS_SELECTOR, "[data-testid*='volume'], .volume-stat")
                for vol_elem in volume_elems:
                    vol_text = vol_elem.text.strip()
                    if '24h' in vol_text.lower():
                        import re
                        match = re.search(r'([\d,]+\.?\d*)', vol_text.replace(',', '').replace(' SOL', ''))
                        if match:
                            result["volume_24h"] = float(match.group(1))
            except Exception:
                # Element not found or parsing failed, continue
                pass
            
            # Image
            try:
                img_elem = driver.find_element(By.CSS_SELECTOR, ".collection-image img, [data-testid='collection-image'] img")
                result["image_url"] = img_elem.get_attribute("src")
            except Exception:
                # Element not found, continue
                pass
            
        except Exception as e:
            logger.debug(f"Magic Eden scraping error: {e}")
        
        return result
    
    def _scrape_solanart(self, driver) -> Dict[str, Any]:
        """Scrape Solanart collection page"""
        result = {}
        # Similar to Magic Eden scraping
        return result
    
    def _scrape_generic(self, driver) -> Dict[str, Any]:
        """Generic scraping fallback"""
        result = {}
        try:
            # Try to get title/name
            try:
                title_elem = driver.find_element(By.TAG_NAME, "h1")
                result["name"] = title_elem.text.strip()
            except Exception:
                # Element not found, continue
                pass
            
            # Try to get description
            try:
                desc_elem = driver.find_element(By.CSS_SELECTOR, "meta[name='description']")
                result["description"] = desc_elem.get_attribute("content")
            except Exception:
                # Element not found, continue
                pass
            
        except Exception as e:
            logger.debug(f"Generic scraping error: {e}")
        
        return result
    
    def close(self):
        """Close WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.debug(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None


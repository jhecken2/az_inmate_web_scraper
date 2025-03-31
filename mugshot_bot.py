import time
import os
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

class InmateScraper:
    def __init__(self, output_dir="inmate_data"):
        chrome_options = Options()
        
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        chrome_options.add_argument(f'user-agent={user_agent}')
        
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": user_agent,
            "acceptLanguage": "en-US,en;q=0.9"
        })
        
        self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'max-age=0',
                'Connection': 'keep-alive',
                'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.google.com/'
            }
        })
        
        self.base_url = "https://inmatedatasearch.azcorrections.gov/"
        
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        self.photos_dir = os.path.join(output_dir, "photos")
        if not os.path.exists(self.photos_dir):
            os.makedirs(self.photos_dir)
            
        self.results_df = pd.DataFrame(columns=["inmate_id", "last_name", "first_name", "admitted_date", "photo_filename"])
    
    def search_inmates(self, last_names, first_initials, gender="Male", status="Active"):
        self.driver.get(self.base_url)
        time.sleep(3)  
        
        for last_name in last_names:
            for first_initial in first_initials:
                print(f"Searching for {last_name}, {first_initial}")
                
                try:
                    inmates = self._perform_search(last_name, first_initial, gender, status)
                    
                    for inmate in inmates:
                        self.results_df = pd.concat([self.results_df, pd.DataFrame([inmate])], ignore_index=True)
                    
                    self.results_df.to_csv(os.path.join(self.output_dir, "inmates.csv"), index=False)
                    
                except Exception as e:
                    print(f"Error searching for {last_name}, {first_initial}: {e}")
                
                delay = random.uniform(2, 5)
                print(f"Waiting {delay:.2f} seconds before next search...")
                time.sleep(delay)
        
        return self.results_df
    
    def _perform_search(self, last_name, first_initial, gender, status):
        self.driver.get(self.base_url)
        
        try:
            search_by_name_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='Search by Name']"))
            )
            search_by_name_btn.click()
            
            last_name_input = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@name='txtLName']"))
            )
            
            last_name_input.clear()
            last_name_input.send_keys(last_name)
            
            first_initial_input = self.driver.find_element(By.XPATH, "//input[@name='txtFName']")
            first_initial_input.clear()
            first_initial_input.send_keys(first_initial)
            
            if gender == "Male":
                self.driver.find_element(By.XPATH, "//input[@value='Male']").click()
            else:
                self.driver.find_element(By.XPATH, "//input[@value='Female']").click()
                
            if status == "Active":
                self.driver.find_element(By.XPATH, "//input[@value='Active']").click()
            else:
                self.driver.find_element(By.XPATH, "//input[@value='Inactive']").click()
            
            self.driver.find_element(By.XPATH, "//input[@value='Search']").click()
            
            time.sleep(3)
            
            inmates = []
            page_count = 0
            
            while True:
                try:
                    table = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//table[@id='gvInmate']"))
                    )
                    
                    rows = table.find_elements(By.XPATH, "//tr[@class='GridViewRow']")
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")[1:]
                        if len(cells) >= 5:
                            try:
                                inmate_id_link = cells[0].find_element(By.TAG_NAME, "a")
                                inmate_id = inmate_id_link.text.strip()
                            except:
                                inmate_id = cells[0].text.strip()
                            
                            try:
                                photo_element = cells[1].find_element(By.TAG_NAME, "input")
                                photo_url = photo_element.get_attribute("src")
                                photo_filename = f"{inmate_id}.jpg"
                                self._download_photo(photo_url, photo_filename)
                            except Exception as e:
                                print(f"Error downloading photo for inmate {inmate_id}: {e}")
                                photo_filename = None
                            
                            last_name = cells[2].text.strip()
                            first_name = cells[3].text.strip()
                            admitted_date = cells[4].text.strip()
                            
                            inmate_data = {
                                "inmate_id": inmate_id,
                                "last_name": last_name,
                                "first_name": first_name,
                                "admitted_date": admitted_date,
                                "photo_filename": photo_filename
                            }
                            
                            inmates.append(inmate_data)
                            print(f"Found inmate: {first_name} {last_name} (ID: {inmate_id})")
                    
                    page_table = table.find_element(By.XPATH, "//td[@colspan='6']")
                    page_links = page_table.find_elements(By.TAG_NAME, "td")
                    if page_links[page_count].text.strip() != str(page_count + 1) or page_count >= len(page_links) - 1:
                        print(f"No more pages to process. Total pages processed: {page_count + 1}")
                        break
                    else:
                        page_count += 1
                        next_page_btn = self.driver.find_element(By.XPATH, f"//a[contains(text(), '{page_count + 1}')]")
                        next_page_btn.click()
                        time.sleep(1)
                
                except Exception as e:
                    print(f"No results found or error: {e}")
                    break
            
            return inmates
            
        except Exception as e:
            print(f"Error during search: {e}")
            return []
    
    def _download_photo(self, url, filename):
        try:
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[1])
            self.driver.get(url)
            
            img_element = self.driver.find_element(By.TAG_NAME, "img")
            img_element.screenshot(os.path.join(self.photos_dir, filename))
            
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            
            print(f"Downloaded photo: {filename}")
            return True
        except Exception as e:
            print(f"Error downloading photo {filename}: {e}")
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            return False
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    scraper = InmateScraper()
    
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", 
                 "Garcia", "Miller", "Davis", "Rodriguez", "Wilson",
                 "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez",
                 "Taylor", "Anderson", "Thomas", "Jackson", "White"]
    first_initials = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
                    "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
                    "U", "V", "W", "X", "Y", "Z"] 
    
    try:
        results = scraper.search_inmates(last_names, first_initials)
        
        print(f"\nFound {len(results)} inmates:")
        for _, inmate in results.iterrows():
            print(f"{inmate['first_name']} {inmate['last_name']} (ID: {inmate['inmate_id']})")
    finally:
        scraper.close()



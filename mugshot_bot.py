import os
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
            
        self.results_df = pd.DataFrame(columns=["inmate_id", "last_name", "first_name_middle_initial", "admitted_date", "photo_filename"])
    
    def search_inmates(self, last_names, first_initials, gender="Male", status="Active"):
        self.driver.get(self.base_url)
        
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
            
            inmates = []
            page_count = 0
            
            while True:
                try:
                    table = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//table[@id='gvInmate']"))
                    )
                    
                    rows = table.find_elements(By.XPATH, "//tr[@class='GridViewRow']")
                    num_rows = len(rows)
                    
                    for i in range(num_rows):
                        table = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//table[@id='gvInmate']"))
                        )
                        rows = table.find_elements(By.XPATH, "//tr[@class='GridViewRow']")
                        cells = rows[i].find_elements(By.TAG_NAME, "td")[1:]
                        if len(cells) >= 5:
                            try:
                                inmate_id_link = cells[0].find_element(By.TAG_NAME, "a")
                                inmate_id = inmate_id_link.text.strip()
                                
                            except Exception as e:
                                print(f"Error accessing inmate details for {inmate_id}: {e}")
                                inmate_id = cells[0].text.strip()
                                photo_filename = None
                            
                            try:
                                photo_element = cells[1].find_element(By.TAG_NAME, "input")
                                photo_url = photo_element.get_attribute("src")
                                photo_filename = f"{inmate_id}.jpg"
                                self._download_photo(photo_url, photo_filename)
                            except Exception:
                                print(f"No inmate photo for inmate {inmate_id}")
                                photo_filename = "None"
                            
                            last_name = cells[2].text.strip()
                            first_name_middle_initial = cells[3].text.strip()
                            admitted_date = cells[4].text.strip()
                            
                            print(f"Navigating to detailed page for inmate {inmate_id}")
                            inmate_id_link.click()
                            
                            # Wait for detailed page to load (look for first info table)
                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GridView8']"))
                            )
                            
                            print(f"Collecting detailed inmate information for inmate {inmate_id}")
                            detailed_info = self._collect_inmate_details()
                            
                            # Save detailed information to respective CSV files
                            self._save_detailed_info(inmate_id, detailed_info)
                            
                            # Go back to search results using browser history
                            self._go_back()
                                                        
                            inmate_data = {
                                "inmate_id": inmate_id,
                                "last_name": last_name,
                                "first_name_middle_initial": first_name_middle_initial,
                                "admitted_date": admitted_date,
                                "photo_filename": photo_filename
                            }
                            inmate_data.update(detailed_info['basic_info'])
                            
                            inmates.append(inmate_data)
                            print(f"Found inmate: {first_name_middle_initial} {last_name} (ID: {inmate_id})")
                    try:
                        table = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//table[@id='gvInmate']"))
                        )                    
                        page_table = table.find_element(By.XPATH, "//td[@colspan='6']")
                        page_links = page_table.find_elements(By.TAG_NAME, "td")
                        if page_links[page_count].text.strip() != str(page_count + 1) or page_count >= len(page_links) - 1:
                            print(f"No more pages to process. Total pages processed: {page_count + 1}")
                            break
                        else:
                            page_count += 1
                            next_page_btn = self.driver.find_element(By.XPATH, f"//a[contains(text(), '{page_count + 1}')]")
                            next_page_btn.click()
                    except Exception:
                        break

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

    def _collect_inmate_details(self):
        """Collect all detailed information from the inmate's page."""
        details = {
            'basic_info': {},
            'sentences': [],
            'infractions': [],
            'appeals': [],
            'classifications': [],
            'work_programs': [],
            'detainers': [],
            'parole_actions': []
        }
        
        try:
            try:
                basic_info_table_1 = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GridView8']")
                basic_info_row_1 = basic_info_table_1.find_element(By.XPATH, ".//tr[@class='GridViewRow']")
                cells = basic_info_row_1.find_elements(By.TAG_NAME, "td")
                details['basic_info'] = {
                    'gender': cells[0].text.strip(),
                    'height': cells[1].text.strip(),
                    'weight': cells[2].text.strip(),
                    'hair_color': cells[3].text.strip()
                }
            except Exception as e:
                print(f"Error collecting first row info: {e}")
                
            try:
                basic_info_table_2 = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GridView9']")
                basic_info_row_2 = basic_info_table_2.find_element(By.XPATH, ".//tr[@class='GridViewRow']")
                cells = basic_info_row_2.find_elements(By.TAG_NAME, "td")
                details['basic_info'].update({
                    'eye_color': cells[0].text.strip(),
                    'ethnic_origin': cells[1].text.strip(),
                    'custody_class': cells[2].text.strip(),
                    'admission': cells[3].text.strip(),
                })
            except Exception as e:
                print(f"Error collecting second row info: {e}")
            
            try:
                basic_info_table_3 = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GridView11']")
                basic_info_row_3 = basic_info_table_3.find_element(By.XPATH, ".//tr[@class='GridViewRow']")
                cells = basic_info_row_3.find_elements(By.TAG_NAME, "td")
                details['basic_info'].update({
                    'release_date': cells[0].text.strip(),
                    'release_type': cells[1].text.strip()
                })
            except Exception as e:
                print(f"Error collecting third row info: {e}")
                
            try:
                basic_info_table_4 = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GridView12']")
                basic_info_row_4 = basic_info_table_4.find_element(By.XPATH, ".//tr[@class='GridViewRow']")
                cells = basic_info_row_4.find_elements(By.TAG_NAME, "td")
                details['basic_info'].update({
                    'complex': cells[0].text.strip(),
                    'unit': cells[1].text.strip(),
                    'last_movement': cells[2].text.strip(),
                    'status': cells[3].text.strip()
                })
            except Exception as e:
                print(f"Error collecting fourth row info: {e}")
                
        except Exception as e:
            print(f"Error collecting inmate details: {e}")

        # Helper function to get record count from section header
        def get_record_count(section_id):
            try:
                header = self.driver.find_element(By.XPATH, f"//span[@id='lbl{section_id}']")
                count_text = header.text.strip()
                return int(count_text.split()[0])
            except Exception:
                return 0

        # Sentences
        sentence_count = get_record_count('Commit')
        if sentence_count > 0:
            try:
                sentence_table = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GVCommitment']")
                sentence_rows = sentence_table.find_elements(By.XPATH, ".//tr[@class='GridViewRow']")
                for row in sentence_rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    details['sentences'].append({
                        'commit_num': cells[0].text.strip(),
                        'sentence_length': cells[1].text.strip(),
                        'county': cells[2].text.strip(),
                        'cause_num': cells[3].text.strip(),
                        'offense_date': cells[4].text.strip(),
                        'sentence_date': cells[5].text.strip(),
                        'sentence_status': cells[6].text.strip(),
                        'crime': cells[7].text.strip()
                    })
            except Exception as e:
                print(f"Error collecting inmate sentences: {e}")

        # Infractions
        infraction_count = get_record_count('Infraction')
        if infraction_count > 0:
            try:
                infraction_table = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GVInfractions']")
                infraction_rows = infraction_table.find_elements(By.XPATH, ".//tr[@class='GridViewRow']")
                for row in infraction_rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    details['infractions'].append({
                        'violation_date': cells[0].text.strip(),
                        'infraction': cells[1].text.strip(),
                        'verdict_date': cells[2].text.strip(),
                        'verdict': cells[3].text.strip()
                    })
            except Exception as e:
                print(f"Error collecting inmate infractions: {e}")

        # Disciplinary Appeals
        appeal_count = get_record_count('Outcome')
        if appeal_count > 0:
            try:
                appeal_table = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GVAppeal']")
                appeal_rows = appeal_table.find_elements(By.XPATH, ".//tr[@class='GridViewRow']")
                for row in appeal_rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    details['appeals'].append({
                        'appeal_date': cells[0].text.strip(),
                        'outcome': cells[1].text.strip(),
                        'as_of_date': cells[2].text.strip()
                    })
            except Exception as e:
                print(f"Error collecting disciplinary appeals: {e}")

        # Classifications
        class_count = get_record_count('Profile')
        if class_count > 0:
            try:
                class_table = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GVProfileClass']")
                class_rows = class_table.find_elements(By.XPATH, ".//tr[@class='GridViewRow']")
                for row in class_rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    details['classifications'].append({
                        'complete_date': cells[0].text.strip(),
                        'classification_type': cells[1].text.strip(),
                        'custody_risk': cells[2].text.strip(),
                        'internal_risk': cells[3].text.strip()
                    })
            except Exception as e:
                print(f"Error collecting inmate classifications: {e}")

        # Parole Actions
        parole_count = get_record_count('ParolAction')
        if parole_count > 0:
            try:
                parole_table = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GVParoleAction']")
                parole_rows = parole_table.find_elements(By.XPATH, ".//tr[@class='GridViewRow']")
                for row in parole_rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    details['parole_actions'].append({
                        'hearing_date': cells[0].text.strip(),
                        'statute': cells[1].text.strip(),
                        'action': cells[2].text.strip()
                    })
            except Exception as e:
                print(f"Error collecting parole actions: {e}")

        # Work Programs
        work_count = get_record_count('Work')
        if work_count > 0:
            try:
                work_table = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GVWorkProgram']")
                work_rows = work_table.find_elements(By.XPATH, ".//tr[@class='GridViewRow']")
                for row in work_rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    details['work_programs'].append({
                        'assigned_date': cells[0].text.strip(),
                        'completed_date': cells[1].text.strip(),
                        'work_assignment': cells[2].text.strip()
                    })
            except Exception as e:
                print(f"Error collecting inmate work programs: {e}")

        # Detainers
        detainer_count = get_record_count('Detainer')
        if detainer_count > 0:
            try:
                detainer_table = self.driver.find_element(By.XPATH, ".//table[contains(@class, 'BorderGridView') and @id='GVDetainer']")
                detainer_rows = detainer_table.find_elements(By.XPATH, ".//tr[@class='GridViewRow']")
                for row in detainer_rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    details['detainers'].append({
                        'detainer_date': cells[0].text.strip(),
                        'detainer_type': cells[1].text.strip(),
                        'charges': cells[2].text.strip(),
                        'authority': cells[3].text.strip(),
                        'agreement_date': cells[4].text.strip()
                    })
            except Exception as e:
                print(f"Error collecting inmate detainers: {e}")

        return details
    
    def _save_detailed_info(self, inmate_id, details):
        """Save detailed information to respective CSV files."""
        try:
            # Create DataFrames for each type of information
            sentences_df = pd.DataFrame(details['sentences'])
            infractions_df = pd.DataFrame(details['infractions'])
            appeals_df = pd.DataFrame(details['appeals'])
            classifications_df = pd.DataFrame(details['classifications'])
            work_programs_df = pd.DataFrame(details['work_programs'])
            detainers_df = pd.DataFrame(details['detainers'])
            parole_actions_df = pd.DataFrame(details['parole_actions'])
            
            # Add inmate_id to each DataFrame
            for df in [sentences_df, infractions_df, appeals_df, classifications_df, 
                      work_programs_df, detainers_df, parole_actions_df]:
                if not df.empty:
                    df.insert(0, 'inmate_id', inmate_id)
            
            # Save to CSV files
            self._append_to_csv(sentences_df, 'sentences.csv')
            self._append_to_csv(infractions_df, 'infractions.csv')
            self._append_to_csv(appeals_df, 'appeals.csv')
            self._append_to_csv(classifications_df, 'classifications.csv')
            self._append_to_csv(work_programs_df, 'work_programs.csv')
            self._append_to_csv(detainers_df, 'detainers.csv')
            self._append_to_csv(parole_actions_df, 'parole_actions.csv')
            
        except Exception as e:
            print(f"Error saving detailed information: {e}")
    
    def _append_to_csv(self, df, filename):
        """Append DataFrame to CSV file."""
        if df.empty:
            return
            
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            df.to_csv(filepath, index=False)
        else:
            df.to_csv(filepath, mode='a', header=False, index=False)
            
    def _go_back(self):
        """Navigate back using browser history instead of the BTIDS button."""
        print("Navigating back...")
        self.driver.execute_script("window.history.go(-1)")

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



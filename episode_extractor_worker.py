from PySide6.QtCore import QObject, Signal
from selenium_utils import SeleniumUtils
import time, re
from selenium.webdriver.common.by import By


class EpisodeExtractorWorker(QObject):
    update_message_signal = Signal(str)
    error_signal = Signal(str)
    finished = Signal()
    update_m3u8_url_signal = Signal(int, str)  # Signal for episode number and m3u8 URL
    error_signal = Signal(str)

    def __init__(self, driver, episode_list_url, initial_episode_count):
        super().__init__()
        self.driver = driver
        self.episode_list_url = episode_list_url
        self.initial_episode_count = initial_episode_count
        self.m3u8_urls_dict = {}  # Dictionary to store m3u8 URLs

    def extract_episodes_list(self):
        episode_number = 1
        try:
            while True:
                print(f"Fetching episode {episode_number}")
                self.driver.get(self.episode_list_url)
                time.sleep(2)
                episode_elements = self.driver.find_elements(By.XPATH, "//div[@id='anime_episodes']/ul//div[@class='sli-name']/a")

                if episode_number == 1 and self.initial_episode_count is None:
                    self.initial_episode_count = len(episode_elements)

                self.update_message_signal.emit(f"Fetching data... (Episode {episode_number}/{self.initial_episode_count})")

                num_episodes = len(episode_elements)
                if num_episodes == 0 or episode_number > self.initial_episode_count:
                    break

                episode_element = episode_elements[num_episodes - episode_number]
                episode_element.click()
                time.sleep(2)
                self.vidcdn(episode_number)  # Assuming this is another function you have
                episode_number += 1
                if episode_number > self.initial_episode_count:
                    print("Reached the total number of episodes, stopping...")
                    break

            self.finished.emit()

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            self.finished.emit()

    def vidcdn(self, episode_number):
        try:
            vidcdn_link_element = SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//a[normalize-space()='VidCDN']", wait_type='visible')
            vidcdn_link = vidcdn_link_element.get_attribute('href')
            self.driver.get(vidcdn_link)

            # Assuming extract_m3u8_full is another method within this class or accessible here
            self.extract_m3u8_full(episode_number)

        except Exception as e:
            print(f"An error occurred in the vidcdn function for Episode {episode_number}: {str(e)}")
            self.error_signal.emit(f"Error in vidcdn for Episode {episode_number}: {str(e)}")

    def extract_m3u8_full(self, episode_number):
        try:
            m3u8_element = SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//span[@class='current']/following-sibling::ul/li[1]", wait_type='present')
            m3u8_raw = m3u8_element.get_attribute("data-value")

            m3u8_regex = r"(https?://.*?\.m3u8)"
            m3u8_match = re.search(m3u8_regex, m3u8_raw)

            if m3u8_match:
                m3u8_url = m3u8_match.group()
                self.m3u8_urls_dict[episode_number] = m3u8_url
                self.update_m3u8_url_signal.emit(episode_number, m3u8_url)

        except Exception as e:
            error_message = f"Error in extract_m3u8 for Episode {episode_number}: {str(e)}"
            print(error_message)
            self.error_signal.emit(error_message)

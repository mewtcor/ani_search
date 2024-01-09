import sys
from PySide6 import QtWidgets
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from PySide6.QtCore import QTimer, Qt, QObject, Slot, QThread
from ui_v2_ani_search import Ui_MainWindow
from PySide6.QtCore import Signal
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import os
import threading
import re
import time

#test
# Define a worker class for episode extraction
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
                self.driver.get(self.episode_list_url)
                time.sleep(2)
                episode_elements = self.driver.find_elements(By.XPATH, "//div[@id='anime_episodes']/ul//div[@class='sli-name']/a")

                if episode_number == 1 and self.initial_episode_count is None:
                    self.initial_episode_count = len(episode_elements)

                num_episodes = len(episode_elements)
                if num_episodes == 0 or episode_number > self.initial_episode_count:
                    break

                episode_element = episode_elements[num_episodes - episode_number]
                episode_element.click()
                time.sleep(2)

                self.vidcdn(episode_number)  # Assuming this is another function you have

                episode_number += 1
                self.update_message_signal.emit(f"Fetching data... (Episode {episode_number}/{self.initial_episode_count})")

                if episode_number > self.initial_episode_count:
                    break

            self.finished.emit()

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            self.finished.emit()

    def vidcdn(self, episode_number):
        try:
            vidcdn_link_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='VidCDN']"))
            )
            vidcdn_link = vidcdn_link_element.get_attribute('href')
            self.driver.get(vidcdn_link)

            # Assuming extract_m3u8_full is another method within this class or accessible here
            self.extract_m3u8_full(episode_number)

        except Exception as e:
            print(f"An error occurred in the vidcdn function for Episode {episode_number}: {str(e)}")
            self.error_signal.emit(f"Error in vidcdn for Episode {episode_number}: {str(e)}")

    def extract_m3u8_full(self, episode_number):
        try:
            m3u8_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//span[@class='current']/following-sibling::ul/li[1]"))
            )
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

class MainWindow(QtWidgets.QMainWindow):
    # Define signals
    update_search_results_signal = Signal(str)
    show_popup_signal = Signal(str)
    update_m3u8_url_signal = Signal(str)
    update_error_message_signal = Signal(str)
    popup_signal = Signal(str, bool)  # Message, and whether to show or hide
    trigger_extract_episode_links = Signal()

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # ... existing setup ...
        self.show_popup_signal.connect(self.show_popup)

        # Initialize Selenium WebDriver
        self.initialize_webdriver()
        
        # Initialize filter_option
        self.filter_option = None  # Add this line to initialize filter_option
        # Connects
        self.ui.btnClose.clicked.connect(self.close_application)
        self.ui.chkSub.clicked.connect(lambda: self.checkbutton_callback('sub'))
        self.ui.chkDub.clicked.connect(lambda: self.checkbutton_callback('dub'))
        self.ui.btnSearch.clicked.connect(self.on_search_clicked)
        self.ui.btnFetchVideo.clicked.connect(self.fetch_video)
        self.ui.btnFetchEpisodes.clicked.connect(self.fetch_episodes)
        self.ui.btnCopy.clicked.connect(self.copy_m3u8_to_clipboard)
        self.ui.btnSelectAnotherEpisode.clicked.connect(self.select_another_episode)
        self.ui.btnPlayOnMPV.clicked.connect(self.play_video)
        self.ui.btnFetchAllVideos.clicked.connect(self.start_extracting_episodes)
        self.ui.btnPlayVideo.clicked.connect(self.play_video_dump)
        # Connect the signal to a slot that updates the UI        
        self.update_search_results_signal.connect(self.update_search_results)
        self.update_m3u8_url_signal.connect(self.update_m3u8_url)
        self.update_error_message_signal.connect(self.update_error_message)
        self.trigger_extract_episode_links.connect(self.extract_episode_links)
        
        # Global variables
        self.episode_list_url = None
        self.search_url = None
        self.totEpisodes = 0
        self.initial_episode_count = None
        self.m3u8_urls_dict = {}
        self.episode_dict = {}
        self.title_elements = []

        # Load initial website and update trending animes
        self.load_initial_website()
        self.update_trending_animes()
        self.update_popular_animes()

    # Slot for updating search results in the UI
    def update_search_results(self, results):
        self.ui.txtBrowserSearchResult.setPlainText(results)

    def initialize_webdriver(self):
        chromedriver_path = os.path.expanduser("~/PythonProjects/scrapers/chromedriver")  # mac
        ublock_origin_path = os.path.expanduser("~/PythonProjects/scrapers/ublock.crx")  # mac
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("window-size=1920x1080")
        chrome_options.add_extension(ublock_origin_path)
        service = Service(executable_path=chromedriver_path, log_path=os.devnull)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        # Minimize Chrome window on macOS
        # self.minimize_chrome()

    def minimize_chrome(self):
        # subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "chrome", "windowminimize"]) # minimize chrome -> this works on linux only
        #---- this is the minimize function for mac that uses applescript command. No xdotool equivalent for mac unfortunately
        applescript_command = '''
        tell application "Google Chrome"
            activate
            repeat with theWindow in (every window)
                tell application "System Events" to keystroke "m" using command down
            end repeat
        end tell
        '''
        subprocess.run(["osascript", "-e", applescript_command])
        #--- end of mac minimize

    def load_initial_website(self):
        try:
            self.driver.get("https://animension.to/")
            print("Initial website loaded successfully.")
        except Exception as e:
            print(f"Error loading initial website: {str(e)}")

    def update_trending_animes(self):
        try:
            # Assuming the website and elements are still the same
            trending_elements = self.driver.find_elements(By.XPATH, "//div[@id='sidebar']/div[1]//ul/li//h4/a[@class='series']")
            trending_animes = [element.text for element in trending_elements]
            self.ui.txtBrowserTrending.setPlainText("\n".join(trending_animes))
        except Exception as e:
            print("Error updating trending animes:", e)

    def update_popular_animes(self):
        try:
            # Assuming the website and elements are still the same
            popular_elements = self.driver.find_elements(By.XPATH, "//div[@id='sidebar']/div[2]//ul/li//h4/a[@class='series']")
            popular_animes = [element.text for element in popular_elements]

            # Update the QTextBrowser in the UI
            self.ui.txtBrowserPopular.setPlainText("\n".join(popular_animes))
        except Exception as e:
            print("Error updating popular animes:", e)

    def on_search_clicked(self):
        # Start the search thread without any filter option
        search_text = self.ui.lineSearch.text()
        # Emit signal to show popup when search starts
        self.show_popup_signal.emit("Searching...")
        threading.Thread(target=self.search_anime, args=(search_text, None)).start()

    def search_anime(self, search_term, filter_option=None):
        try:
            self.driver.get("https://animension.to/")

            # Interacting with PySide6 widgets / chromedriver
            search_box = self.driver.find_element(By.XPATH, "//input[@class='search-live']")
            search_box.send_keys(search_term)
            submit_button = self.driver.find_element(By.XPATH, "//button[@id='submit']")
            submit_button.click()
            # self.ui.btnSearch.click()  # Assuming you have a button named btnSearch

            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//ul[@class='ulclear az-list']"))
            )

            # After performing the search, update the global variable with the current URL
            self.search_url = self.driver.current_url

            # Apply filter based on checkbox selection
            if filter_option == 'sub':
                self.driver.get(self.search_url + "&dub=0")
            elif filter_option == 'dub':
                self.driver.get(self.search_url + "&dub=1")

            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//ul[@class='ulclear az-list']"))
            )

            titles_xpath = "//div[@id='listupd']/div/div//a/div[@class='tt']"
            self.title_elements = self.driver.find_elements(By.XPATH, titles_xpath)

            if not self.title_elements:
                self.update_search_results_signal.emit("No search results found. Please try again.\n")
                return

            search_results = "\n".join(f"{index}. {title.text}" for index, title in enumerate(self.title_elements, start=1))
            self.update_search_results_signal.emit(search_results)

        except Exception as e:
            self.update_search_results_signal.emit(f"Error: {str(e)}\n")

    def fetch_video(self):
        episode_number = self.ui.lineChosenEpisode.text()
        if not episode_number.isdigit() or int(episode_number) not in range(1, len(self.episode_dict) + 1):
            self.ui.txtBrowserEpisodes.append("Invalid episode. Please enter a valid number.\n")
            return
        
        self.episode_number = int(episode_number)  # Set the episode number here
        episode_link = self.episode_dict[episode_number]
        episode_link.click()

        # Start a new thread to scrape m3u8
        threading.Thread(target=self.scrape_m3u8, args=(episode_link,)).start()

        # Disable lineChosenEpisode
        self.ui.lineChosenEpisode.setReadOnly(True)

    def fetch_episodes(self):
        self.show_popup_signal.emit("Searching...")

        choice = self.ui.lineAnimeChoice.text()
        if not choice.isdigit() or int(choice) - 1 not in range(len(self.title_elements)):
            self.update_error_message_signal.emit("Invalid choice. Please enter a valid number.\n")
            return

        selected_index = int(choice) - 1
        selected_title_element = self.title_elements[selected_index]
        selected_title_element.click()

        # After successfully loading the episodes and confirming the URL
        self.episode_list_url = self.driver.current_url
        # handle episode extraction
        self.extract_episode_links()

    def extract_episode_links(self):
        try:
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//div[@id='anime_episodes']/ul//div[@class='sli-name']/a"))
            )
            episode_links = self.driver.find_elements(By.XPATH, "//div[@id='anime_episodes']/ul//div[@class='sli-name']/a")
            print("Number of episode links found:", len(episode_links))  # Debugging print

            self.episode_dict = {link.text.split(' - ')[0].split(' ')[1]: link for link in episode_links}

            if not episode_links:
                print("No episode links found.")
                return

            episode_info = "\n".join(f"{ep_num}: {link.text}" for ep_num, link in self.episode_dict.items())
            self.ui.txtBrowserEpisodes.setPlainText(episode_info)
            self.count_total_episodes()

        except Exception as e:
            print(f"Error extracting episode links: {e}")

    def count_total_episodes(self):
        episodes_text_content = self.ui.txtBrowserEpisodes.toPlainText()
        # Split the content into lines and count the number of non-empty lines
        self.totEpisodes = len([line for line in episodes_text_content.splitlines() if line.strip()])

        # Print the total episode count to the console
        print(f"Total Episodes: {self.totEpisodes}")

    def scrape_m3u8(self, episode_link):
        try:
            vidcdn_link_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='VidCDN']"))
            )
            vidcdn_link = vidcdn_link_element.get_attribute('href')
            self.driver.get(vidcdn_link)

            vidcdn_value_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//span[@class='current']/following-sibling::ul/li[1]"))
            )
            vidcdn_value = vidcdn_value_element.get_attribute('data-value')

            m3u8_regex = r"(https?://.*?\.m3u8)"
            m3u8_match = re.search(m3u8_regex, vidcdn_value)
            # Assume m3u8_url is obtained
            if m3u8_match:
                m3u8_url = m3u8_match.group()
                self.m3u8_urls_dict[self.episode_number] = m3u8_match.group()
                self.update_m3u8_url_signal.emit(m3u8_url)
            else:
                self.update_error_message_signal.emit("No m3u8 link found in the URL.")
        except Exception as e:
            self.update_error_message_signal.emit(f"Error: {str(e)}")

    def update_m3u8_url(self, m3u8_url):
        self.ui.lineM3u8.setText(m3u8_url)
        self.ui.btnSelectAnotherEpisode.setEnabled(True)

    def fetch_video_thread(self):
        try:
            self.fetch_video()
        except Exception as e:
            print(f"Error in fetch_video: {e}")

    def select_another_episode(self):
        self.ui.lineChosenEpisode.clear()
        self.ui.lineChosenEpisode.setReadOnly(False)
        self.ui.txtBrowserEpisodes.clear()
        self.ui.lineM3u8.clear()
        if self.episode_list_url:
            self.driver.get(self.episode_list_url)

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//div[@id='anime_episodes']"))
                )
                # Emit the signal
                self.trigger_extract_episode_links.emit()

            except Exception as e:
                print("Error while waiting for the episode list page to load:", e)

    def play_video(self):
        print("play_video called")  # Debugging print
        print("m3u8_urls_dict:", self.m3u8_urls_dict)  # Debugging print
        episode_number = self.ui.lineChosenEpisode.text()
        print(f"Episode number: {episode_number}")  # Debugging print

        if episode_number.isdigit():
            episode_number = int(episode_number)
            if episode_number in self.m3u8_urls_dict:
                m3u8_url = self.m3u8_urls_dict[episode_number]
                print(f"Playing URL: {m3u8_url}")  # Debugging print
                subprocess.run(["mpv", m3u8_url])
            else:
                print("Video not found for the selected episode.")  # Debugging print
                self.show_centered_popup_message("Video not found for the selected episode.")
        else:
            print("Please enter a valid episode number.")  # Debugging print
            self.show_centered_popup_message("Please enter a valid episode number.")\

    def play_video_dump(self):
        episode_number = self.ui.lineAllVidsSelection.text()  # Use lineAllVidsSelection for episode number
        print("Current m3u8_urls_dict:", self.m3u8_urls_dict)  # Print the current state of m3u8_urls_dict

        if episode_number.isdigit():
            episode_number = int(episode_number)
            if episode_number in self.m3u8_urls_dict:
                m3u8_url = self.m3u8_urls_dict[episode_number]
                subprocess.run(["mpv", m3u8_url])
            else:
                self.show_centered_popup_message("Video not found for the selected episode.")
        else:
            self.show_centered_popup_message("Please enter a valid episode number.")

    def handle_m3u8_url_update(self, episode_number, m3u8_url):
        self.m3u8_urls_dict[episode_number] = m3u8_url
        print(f"Updated m3u8_urls_dict: {self.m3u8_urls_dict}")

    def update_error_message(self, message):
        self.ui.lineM3u8.setText(message)
        self.ui.btnSelectAnotherEpisode.setEnabled(True)
        self.ui.txtBrowserEpisodes.append(message)

    def on_btnFetchVideo_clicked(self):
        # Start the fetch_video_thread
        threading.Thread(target=self.fetch_video_thread).start()

    def checkbutton_callback(self, option):
        # Set the filter option
        if option == 'sub':
            self.ui.chkDub.setChecked(False)
            self.filter_option = 'sub'
        elif option == 'dub':
            self.ui.chkSub.setChecked(False)
            self.filter_option = 'dub'

        # Start the search thread with the filter option
        search_text = self.ui.lineSearch.text()
        threading.Thread(target=self.search_anime, args=(search_text, self.filter_option)).start()

    def show_centered_popup_message(self, message):
        popup = QDialog(self)
        popup.setWindowTitle("Message")
        popup.setFixedSize(300, 100)

        label = QLabel(message, popup)
        label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(label)
        popup.setLayout(layout)

        # Calculate the center position of the screen
        screen_geometry = self.screen().geometry()
        x = (screen_geometry.width() - popup.width()) // 2
        y = (screen_geometry.height() - popup.height()) // 2
        popup.move(x, y)

        # Automatically close the popup after 3 seconds (adjust as needed)
        QTimer.singleShot(3000, popup.close)

        popup.show()

    def show_popup(self, message):
        # Method to show popup, now executed in the main thread
        self.show_centered_popup_message(message)

    def copy_m3u8_to_clipboard(self):
        m3u8_text = self.ui.lineM3u8.text()  # Get the text from lineM3u8
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(m3u8_text)  # Copy the text to the clipboard

    def close_application(self):
        if hasattr(self, 'driver'):
            self.driver.quit()  # This will close the Selenium WebDriver
        self.close()  # This will close the main window

    def closeEvent(self, event):
        # Perform cleanup actions before closing the window
        self.cleanup_resources()
        event.accept()  # Accept the close event
    
    def cleanup_resources(self):
        # Close the Selenium WebDriver if it exists
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except Exception as e:
                print(f"Error closing WebDriver: {e}")

    def start_extracting_episodes(self):
        self.thread = QThread()
        self.worker = EpisodeExtractorWorker(self.driver, self.episode_list_url, self.initial_episode_count)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.extract_episodes_list)
        self.worker.update_message_signal.connect(self.update_fetching_popup)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.on_extraction_finished)
        self.worker.error_signal.connect(self.handle_vidcdn_error)
        self.worker.update_m3u8_url_signal.connect(self.handle_m3u8_url_update)
        # Move the worker to the thread and start it
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.extract_episodes_list)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

        # Initialize and show fetching popup
        self.fetching_popup = QDialog(self)
        self.fetching_popup.setWindowTitle("Fetching Data")
        self.fetching_label = QLabel("Fetching data...", self.fetching_popup)
        self.fetching_label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self.fetching_popup)
        layout.addWidget(self.fetching_label)
        self.fetching_popup.setLayout(layout)
        self.fetching_popup.setFixedSize(300, 100)
        self.fetching_popup.show()

    @Slot(str)
    def update_fetching_popup(self, message):
        self.fetching_label.setText(message)

    @Slot()
    def on_extraction_finished(self):
        self.fetching_popup.close()
        self.show_centered_popup_message("Videos are ready!")

    @Slot(str)
    def handle_vidcdn_error(self, message):
        # Handle the error, maybe display it in the UI
        print(message)
        # Update the UI as needed

    @Slot(int, str)
    def handle_m3u8_url_update(self, episode_number, m3u8_url):
        self.m3u8_urls_dict[episode_number] = m3u8_url
        print(f"Updated m3u8_urls_dict: {self.m3u8_urls_dict}")

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()

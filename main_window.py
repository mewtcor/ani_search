# from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QObject, QThread, QUrl
from PySide6 import QtWidgets
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from ui_v2_ani_search import Ui_MainWindow
from episode_extractor_worker import EpisodeExtractorWorker
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.common.by import By
import os, threading,re, subprocess
from selenium_utils import SeleniumUtils
from PySide6.QtGui import QPixmap, QImage
import settings

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
        self.setup_ui_connections()
        self.initialize_webdriver()
        self.load_initial_website()
        self.update_trending_and_popular_animes()

        self.ui.lineSearch.setFocus()
        # Disable all QPushButtons and QLineEdits except for lineSearch, btnSearch, and btnClose
        for widget in self.ui.centralwidget.findChildren(QtWidgets.QPushButton):
            if widget not in [self.ui.btnSearch, self.ui.btnClose]:
                widget.setEnabled(False)

        for widget in self.ui.centralwidget.findChildren(QtWidgets.QLineEdit):
            if widget is not self.ui.lineSearch:
                widget.setEnabled(False)

        # Initialize QNetworkAccessManager for image downloading
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self.on_image_download_finished)

        # Global variables
        self.episode_list_url = None
        self.search_url = None
        self.totEpisodes = 0
        self.initial_episode_count = None
        self.m3u8_urls_dict = {}
        self.episode_dict = {}
        self.title_elements = []
        self.filter_option = None
        self.thread = None  # Initialize thread attribute

    def setup_ui_connections(self):
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
        self.update_search_results_signal.connect(self.update_search_results)
        self.update_m3u8_url_signal.connect(self.update_m3u8_url)
        self.update_error_message_signal.connect(self.update_error_message)
        self.trigger_extract_episode_links.connect(self.extract_episode_links)
        self.show_popup_signal.connect(self.show_popup)


    def update_trending_and_popular_animes(self):
        self.update_anime_list("trending", "//div[@id='sidebar']/div[1]//ul/li//h4/a[@class='series']")
        self.update_anime_list("popular", "//div[@id='sidebar']/div[2]//ul/li//h4/a[@class='series']")

    def update_anime_list(self, type, xpath):
        try:
            elements = self.driver.find_elements(By.XPATH, xpath)
            animes = [element.text for element in elements]
            if type == "trending":
                self.ui.txtBrowserTrending.setPlainText("\n".join(animes))
            elif type == "popular":
                self.ui.txtBrowserPopular.setPlainText("\n".join(animes))
        except Exception as e:
            print(f"Error updating {type} animes:", e)
    
    # Slot for updating search results in the UI
    def update_search_results(self, results):
        self.ui.txtBrowserSearchResult.setPlainText(results)
        # self.update_ui_state_based_on_search_results()
        # Check if search results contain episodes or the no results message
        if "No search results found" in results:
            self.set_search_related_widgets_enabled(False)
        else:
            self.set_search_related_widgets_enabled(True)
            # Set focus to lineAnimeChoice if there are episodes
            self.ui.lineAnimeChoice.setFocus()

    def set_search_related_widgets_enabled(self, enabled):
        self.ui.btnFetchEpisodes.setEnabled(enabled)
        self.ui.lineAnimeChoice.setEnabled(enabled)
        self.ui.chkDub.setEnabled(enabled)
        self.ui.chkSub.setEnabled(enabled)

    def initialize_webdriver(self):
        chrome_options = self.get_chrome_options()
        service = self.get_chrome_service()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        # self.minimize_browser_window()

    def get_chrome_options(self):
        # ublock_origin_path = os.path.expanduser("~/PythonProjects/scrapers/ublock.crx")  # mac
        ublock_origin_path = settings.UBLOCK_ORIGIN_PATH
        chrome_options = Options()
        chrome_options.add_argument("window-size=1920x1080")
        # chrome_options.add_argument("--headless")
        chrome_options.add_extension(ublock_origin_path)
        return chrome_options

    def get_chrome_service(self):
        # chromedriver_path = os.path.expanduser("~/PythonProjects/scrapers/chromedriver")  # mac
        chromedriver_path = settings.CHROMEDRIVER_PATH
        return Service(executable_path=chromedriver_path, log_path=os.devnull)

    def minimize_browser_window(self):
        # Implement platform-specific window minimization
        # --> linux 
        subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "chrome", "windowminimize"]) # minimize chrome -> this works on linux only
        
        #---- this is the minimize function for mac that uses applescript command. No xdotool equivalent for mac unfortunately
        # applescript_command = '''
        # tell application "Google Chrome"
        #     activate
        #     repeat with theWindow in (every window)
        #         tell application "System Events" to keystroke "m" using command down
        #     end repeat
        # end tell
        # '''
        # subprocess.run(["osascript", "-e", applescript_command])

    def load_initial_website(self):
        try:
            self.driver.get(settings.INITIAL_URL)
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
        
        # Clear and lock UI elements
        self.clear_and_lock_ui()

    def clear_and_lock_ui(self):
    # Loop through and lock QPushButton, QLineEdit, QTextBrowser, QCheckBox, QGraphicsView
        for widget in self.ui.centralwidget.findChildren(QtWidgets.QWidget):
            if isinstance(widget, (QtWidgets.QPushButton, QtWidgets.QLineEdit, QtWidgets.QTextBrowser, QtWidgets.QCheckBox, QtWidgets.QGraphicsView)):
                if widget not in [self.ui.btnSearch, self.ui.btnClose, self.ui.txtBrowserTrending, self.ui.txtBrowserPopular, self.ui.lineSearch]:
                    widget.setProperty("locked", True)
                    widget.setStyleSheet("background-color: #f0f0f0;")  # Example: Change background color to indicate locked state
                    if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QTextBrowser)):
                        widget.clear()


    def update_ui_state_based_on_search_results(self):
        search_results = self.ui.txtBrowserSearchResult.toPlainText()
        has_episodes = len(search_results.strip()) > 0  # Simple check, modify as needed based on actual content structure

        self.ui.btnFetchEpisodes.setEnabled(has_episodes)
        self.ui.lineAnimeChoice.setEnabled(has_episodes)


    def search_anime(self, search_term, filter_option=None):
        try:
            self.driver.get("https://animension.to/")

            # Interacting with PySide6 widgets / chromedriver
            search_box = self.driver.find_element(By.XPATH, "//input[@class='search-live']")
            search_box.send_keys(search_term)
            submit_button = self.driver.find_element(By.XPATH, "//button[@id='submit']")
            submit_button.click()
            # self.ui.btnSearch.click()  # Assuming you have a button named btnSearch

            SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//ul[@class='ulclear az-list']", wait_type='visible')

            # After performing the search, update the global variable with the current URL
            self.search_url = self.driver.current_url

            # Apply filter based on checkbox selection
            if filter_option == 'sub':
                self.driver.get(self.search_url + "&dub=0")
            elif filter_option == 'dub':
                self.driver.get(self.search_url + "&dub=1")

            SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//ul[@class='ulclear az-list']", wait_type='visible')

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

        # Check if lineM3u8 is populated and update UI elements
        # self.update_ui_state_after_fetch_video()

    def update_ui_state_after_fetch_video(self):
        m3u8_url = self.ui.lineM3u8.text()
        print(f"Updating UI state, m3u8 URL: '{m3u8_url}'")  # Debugging line

        if m3u8_url.strip():  # Added strip() to ensure it's not just whitespace
            self.ui.btnSelectAnotherEpisode.setEnabled(True)
            self.ui.btnPlayOnMPV.setEnabled(True)
            self.ui.btnCopy.setEnabled(True)
        else:
            self.ui.btnSelectAnotherEpisode.setEnabled(False)
            self.ui.btnPlayOnMPV.setEnabled(False)
            self.ui.btnCopy.setEnabled(False)

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
        self.update_ui_state_after_fetch_episodes()
        self.episode_list_url = self.driver.current_url
        self.extract_ani_info()  # Call extract_ani_info method        
        self.extract_episode_links() # handle episode extraction
        self.ui.lineChosenEpisode.setFocus()

    def update_ui_state_after_fetch_episodes(self):
        episodes_text = self.ui.txtBrowserEpisodes.toPlainText()
        if "Invalid choice. Please enter a valid number." not in episodes_text:
            self.ui.lineChosenEpisode.setEnabled(True)
            self.ui.btnFetchVideo.setEnabled(True)
            self.ui.btnFetchAllVideos.setEnabled(True)
        else:
            self.ui.lineChosenEpisode.setEnabled(False)
            self.ui.btnFetchVideo.setEnabled(False)
            self.ui.btnFetchAllVideos.setEnabled(False)

    def extract_ani_info(self):
        try:
            # Extract and update anime title
            ani_title_element = self.driver.find_element(By.XPATH, "//h1[@class='entry-title']")
            self.ui.lblAniTitle.setText(ani_title_element.text)

            # Start image download
            ani_image_element = self.driver.find_element(By.XPATH, "//div[@id='thumbook']/div[1]//img")
            ani_image_url = ani_image_element.get_attribute('src')
            self.network_manager.get(QNetworkRequest(QUrl(ani_image_url)))

            # Extract and update anime description
            ani_description_element = self.driver.find_element(By.XPATH, "//div[@class='desc']")
            ani_description = ani_description_element.text.strip()
            self.ui.txtAniDescription.setPlainText(ani_description)

            # Extract Rating
            ani_rating_element = self.driver.find_element(By.XPATH, "//div[@class='rating']//strong")
            self.ui.lblMALScore.setText(ani_rating_element.text)

        except Exception as e:
            print(f"Error extracting anime info: {e}")

    def on_image_download_finished(self, reply):
        # Slot to handle the downloaded image data
        error = reply.error()

        if error == QNetworkReply.NoError:
            data = reply.readAll()
            image = QImage()
            image.loadFromData(data)

            pixmap = QPixmap.fromImage(image)
            scene = QGraphicsScene(self)
            item = QGraphicsPixmapItem(pixmap)
            scene.addItem(item)
            self.ui.viewAniThumbnail.setScene(scene)
            self.ui.viewAniThumbnail.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        else:
            print(f"Failed to download image: {reply.errorString()}")

    def extract_episode_links(self):
        try:
            SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//div[@id='anime_episodes']/ul//div[@class='sli-name']/a", wait_type='visible')
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
            vidcdn_link_element = SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//a[normalize-space()='VidCDN']", wait_type='visible')
            vidcdn_link = vidcdn_link_element.get_attribute('href')
            self.driver.get(vidcdn_link)

            vidcdn_value_element = SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//span[@class='current']/following-sibling::ul/li[1]", wait_type='present')
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
        # self.ui.btnSelectAnotherEpisode.setEnabled(True)
        self.update_ui_state_after_fetch_video()
    def fetch_video_thread(self):
        try:
            self.fetch_video()
        except Exception as e:
            print(f"Error in fetch_video: {e}")

    def select_another_episode(self):
        self.ui.lineChosenEpisode.clear()
        self.ui.lineChosenEpisode.setEnabled(True)
        self.ui.lineChosenEpisode.setReadOnly(False)
        self.ui.lineChosenEpisode.setFocus()
        self.ui.txtBrowserEpisodes.clear()
        self.ui.lineM3u8.clear()

        # Lock the other UI elements
        self.ui.btnSelectAnotherEpisode.setEnabled(False)
        self.ui.btnPlayOnMPV.setEnabled(False)

        if self.episode_list_url:
            self.driver.get(self.episode_list_url)

            try:
                SeleniumUtils.wait_for_element(self.driver, By.XPATH, "//div[@id='anime_episodes']", wait_type='visible')
                # Emit the signal
                self.trigger_extract_episode_links.emit()

            except Exception as e:
                print("Error while waiting for the episode list page to load:", e)

    def play_video(self):
        print("play_video called")
        episode_number = self.ui.lineChosenEpisode.text()

        if episode_number.isdigit():
            episode_number = int(episode_number)
            if episode_number in self.m3u8_urls_dict:
                m3u8_url = self.m3u8_urls_dict[episode_number]
                print(f"Playing URL: {m3u8_url}")

                # Start MPV player in a separate thread
                threading.Thread(target=self.launch_mpv_player, args=(m3u8_url,)).start()
            else:
                print("Video not found for the selected episode.")
                self.show_centered_popup_message("Video not found for the selected episode.")
        else:
            print("Please enter a valid episode number.")
            self.show_centered_popup_message("Please enter a valid episode number.")

    
    def launch_mpv_player(self, url):
        # Start MPV player in a non-blocking way
        subprocess.Popen(["mpv", url], start_new_session=True)

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

    def update_error_message(self, message):
        self.ui.lineM3u8.setText(message)
        # self.ui.btnSelectAnotherEpisode.setEnabled(True)
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
        self.on_btnFetchAllVideos_clicked()

        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            print("Extraction process is already running.")
            return

        print("function: start_extracting_episodes test")
        self.thread = QThread()
        self.worker = EpisodeExtractorWorker(self.driver, self.episode_list_url, self.initial_episode_count)

        # Connect signals and slots
        self.thread.started.connect(self.worker.extract_episodes_list)
        self.worker.update_message_signal.connect(self.update_fetching_popup)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error_signal.connect(self.handle_vidcdn_error)
        self.worker.update_m3u8_url_signal.connect(self.handle_m3u8_url_update)
        # Connect the finished signal of both worker and thread to on_extraction_finished
        self.worker.finished.connect(self.on_extraction_finished)
        self.thread.finished.connect(self.on_extraction_finished)

        # Move the worker to the thread
        self.worker.moveToThread(self.thread)

        # Handling thread termination
        self.thread.finished.connect(self.on_thread_finished)

        # Initialize and show fetching popup
        self.show_fetching_popup()

        # Start the thread
        self.thread.start()

    def on_btnFetchAllVideos_clicked(self):
        # Lock the buttons
        self.ui.btnFetchVideo.setEnabled(False)
        self.ui.btnCopy.setEnabled(False)
        self.ui.btnPlayOnMPV.setEnabled(False)
        self.ui.btnSelectAnotherEpisode.setEnabled(False)

        # Clear and lock line edits
        self.ui.lineM3u8.clear()
        self.ui.lineM3u8.setEnabled(False)
        self.ui.lineChosenEpisode.clear()
        self.ui.lineChosenEpisode.setEnabled(False)

    def on_thread_finished(self):
        print("Thread finished.")
        self.thread = None  # Reset the thread to allow for future executions

    def show_fetching_popup(self):
        self.fetching_popup = QDialog(self)
        self.fetching_popup.setWindowTitle("Fetching Data")
        self.fetching_label = QLabel("Fetching data...", self.fetching_popup)
        self.fetching_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self.fetching_popup)
        layout.addWidget(self.fetching_label)
        self.fetching_popup.setLayout(layout)
        self.fetching_popup.setFixedSize(300, 100)
        self.fetching_popup.show()

    def on_extraction_finished(self):
        # Close the fetching popup and reset thread and worker
        if self.fetching_popup:
            self.fetching_popup.close()
            self.fetching_popup = None
        self.thread = None
        self.worker = None
        print("Extraction finished.")

    @Slot(str)
    def update_fetching_popup(self, message):
        self.fetching_label.setText(message)

    @Slot()
    def on_extraction_finished(self):
        self.fetching_popup.close()
        self.show_centered_popup_message("Videos are ready!")
        # Unlock btnPlayVideo
        self.ui.btnPlayVideo.setEnabled(True)
        self.ui.lineAllVidsSelection.setEnabled(True)
        self.ui.lineAllVidsSelection.setFocus()
        
    @Slot(str)
    def handle_vidcdn_error(self, message):
        # Handle the error, maybe display it in the UI
        print(message)
        # Update the UI as needed

    @Slot(int, str)
    def handle_m3u8_url_update(self, episode_number, m3u8_url):
        self.m3u8_urls_dict[episode_number] = m3u8_url
        # print(f"Updated m3u8_urls_dict: {self.m3u8_urls_dict}")

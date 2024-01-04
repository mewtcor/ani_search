import tkinter as tk
from tkinter import scrolledtext, messagebox, Toplevel
import threading
import subprocess
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time
import os
import platform
import subprocess


# Initialize WebDriver
chromedriver_path = r"/home/m3wt/vesta/python/scrapers/chromedriver"
ublock_origin_path = r'/home/m3wt/vesta/python/scrapers/ublock.crx'
chrome_options = Options()
# chrome_options.add_argument("--headless")
chrome_options.add_argument("window-size=1920x1080")  # Set a window size
chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')  # Set a user-agent
chrome_options.add_extension(ublock_origin_path)
service = Service(executable_path=chromedriver_path, log_path=os.devnull)
driver = webdriver.Chrome(service=service, options=chrome_options)

subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "chrome", "windowminimize"])


# Global variable to store the episode list URL
episode_list_url = None
search_url = None  # New global variable to store the search URL
totEpisodes = 0
initial_episode_count = None
m3u8_urls_dict = {}

def load_initial_website():
    try:
        driver.get("https://animension.to/")
        print("Initial website loaded successfully.")
    except Exception as e:
        print(f"Error loading initial website: {str(e)}")

def checkbutton_callback(option):
    if option == 'sub':
        dub_var.set(0)
        filter_option = 'sub'
    elif option == 'dub':
        sub_var.set(0)
        filter_option = 'dub'
    
    threading.Thread(target=search_anime, args=(search_entry.get(), results_text, episodes_text, m3u8_entry, filter_option)).start()

def search_anime(search_term, results_text, episodes_text, m3u8_entry, filter_option=None):
    try:
        driver.get("https://animension.to/")

        # Show a "Searching..." popup message
        show_centered_popup_message("Searching...")

        search_box = driver.find_element(By.XPATH, "//input[@class='search-live']")
        search_box.send_keys(search_term)
        submit_button = driver.find_element(By.XPATH, "//button[@id='submit']")
        submit_button.click()

        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//ul[@class='ulclear az-list']"))
        )

        # After performing the search, update the global variable with the current URL
        search_url = driver.current_url

        # Apply filter based on checkbox selection
        if filter_option == 'sub':
            driver.get(search_url + "&dub=0")
        elif filter_option == 'dub':
            driver.get(search_url + "&dub=1")

        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//ul[@class='ulclear az-list']"))
        )

        titles_xpath = "//div[@id='listupd']/div/div//a/div[@class='tt']"
        title_elements = driver.find_elements(By.XPATH, titles_xpath)

        if not title_elements:
            results_text.config(state=tk.NORMAL)
            results_text.insert(tk.END, "No search results found. Please try again.\n")
            results_text.config(state=tk.DISABLED)
            return

        results_text.config(state=tk.NORMAL)
        results_text.delete('1.0', tk.END)
        for index, title in enumerate(title_elements, start=1):
            results_text.insert(tk.END, f"{index}. {title.text}\n")
        results_text.config(state=tk.DISABLED)

        root.choice = tk.StringVar()
        choice_entry.config(textvariable=root.choice)

        root.title_elements = title_elements
        root.episodes_text = episodes_text
        root.m3u8_entry = m3u8_entry
    except Exception as e:
        results_text.config(state=tk.NORMAL)
        results_text.insert(tk.END, f"Error: {str(e)}\n")
        results_text.config(state=tk.DISABLED)

def fetch_episodes():
    global episode_list_url

    # Show a "Searching..." popup message
    show_centered_popup_message("Searching...")

    choice = root.choice.get()
    if not choice.isdigit() or int(choice) - 1 not in range(len(root.title_elements)):
        results_text.config(state=tk.NORMAL)
        results_text.insert(tk.END, "Invalid choice. Please enter a valid choice(number).\n")
        results_text.config(state=tk.DISABLED)
        return

    selected_title = root.title_elements[int(choice) - 1]
    selected_title.click()

    # Call a new function to handle episode extraction
    extract_episode_links()

def count_total_episodes():
    global totEpisodes
    episodes_text_content = episodes_text.get("1.0", tk.END)
    # Split the content into lines and count the number of non-empty lines
    totEpisodes = len([line for line in episodes_text_content.splitlines() if line.strip()])
    
    # Print the total episode count to the console
    print(f"Total Episodes: {totEpisodes}")

def extract_episode_links():
    global episode_list_url

    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, "//div[@id='anime_episodes']"))
    )

    episode_links = driver.find_elements(By.XPATH, "//div[@id='anime_episodes']/ul//div[@class='sli-name']/a")
    episode_dict = {link.text.split(' - ')[0].split(' ')[1]: link for link in episode_links}

    episodes_text.config(state=tk.NORMAL)
    episodes_text.delete('1.0', tk.END)
    for episode_number, link in episode_dict.items():
        episodes_text.insert(tk.END, f"{episode_number}: {link.get_attribute('href')}\n")
    episodes_text.config(state=tk.DISABLED)

    root.episode_dict = episode_dict
    root.episode_choice = tk.StringVar()
    episode_entry.config(textvariable=root.episode_choice)

    # Store the episode list URL
    episode_list_url = driver.current_url

    # Count the total episodes
    count_total_episodes()


def select_another_episode():
    global episode_list_url

    # Unlock the episode_entry
    episode_entry.config(state='normal')

    # Clear episodes_text if it is populated
    if episodes_text.get("1.0", tk.END).strip():
        episodes_text.config(state=tk.NORMAL)
        episodes_text.delete("1.0", tk.END)
        episodes_text.config(state=tk.DISABLED)

    # Clear m3u8_entry if it is populated
    if m3u8_entry.get():
        m3u8_entry.config(state=tk.NORMAL)
        m3u8_entry.delete(0, tk.END)
        m3u8_entry.config(state='readonly')

    if episode_list_url:
        driver.get(episode_list_url)
        time.sleep(5)
        extract_episode_links()

# Define a dictionary to store the m3u8 URLs
m3u8_urls_dict = {}

def scrape_m3u8(episode_link):
    try:
        vidcdn_link_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='VidCDN']"))
        )
        vidcdn_link = vidcdn_link_element.get_attribute('href')
        driver.get(vidcdn_link)

        vidcdn_value_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[@class='current']/following-sibling::ul/li[1]"))
        )
        vidcdn_value = vidcdn_value_element.get_attribute('data-value')

        m3u8_regex = r"(https?://.*?\.m3u8)"
        m3u8_match = re.search(m3u8_regex, vidcdn_value)
        if m3u8_match:
            m3u8_url = m3u8_match.group()
            root.m3u8_entry.config(state=tk.NORMAL)
            root.m3u8_entry.delete(0, tk.END)
            root.m3u8_entry.insert(0, m3u8_url)
            root.m3u8_entry.config(state='readonly')
            select_another_episode_button.config(state=tk.NORMAL)
        else:
            root.m3u8_entry.config(state=tk.NORMAL)
            root.m3u8_entry.delete(0, tk.END)
            root.m3u8_entry.insert(0, "No m3u8 link found in the URL.")
            root.m3u8_entry.config(state='readonly')
            select_another_episode_button.config(state=tk.NORMAL)
    except Exception as e:
        root.m3u8_entry.config(state=tk.NORMAL)
        root.m3u8_entry.delete(0, tk.END)
        root.m3u8_entry.insert(0, f"Error: {str(e)}")
        root.m3u8_entry.config(state='readonly')
        select_another_episode_button.config(state=tk.NORMAL)



def fetch_video():
    episode_number = root.episode_choice.get()
    if not episode_number.isdigit() or int(episode_number) not in range(1, len(root.episode_dict) + 1):
        episodes_text.config(state=tk.NORMAL)
        episodes_text.insert(tk.END, "Invalid episode. Please enter a valid number.\n")
        episodes_text.config(state=tk.DISABLED)
        return

    episode_link = root.episode_dict[episode_number]  # Get the episode link
    episode_link.click()  # Click the episode link

    # Pass the episode link to the scrape_m3u8 function
    threading.Thread(target=scrape_m3u8, args=(episode_link,)).start()

    # Lock the episode_entry at the end
    episode_entry.config(state='readonly')

def play_mpv():
    m3u8_url = m3u8_entry.get()
    if m3u8_url.startswith("https"):
        subprocess.run(["mpv", m3u8_url])
    else:
        messagebox.showerror("Error", "Invalid M3U8 URL")

def update_trending_animes():
    try:
        # driver.get("https://animension.to/")  # Or the relevant URL for your site
        trending_elements = driver.find_elements(By.XPATH, "//div[@id='sidebar']/div[1]//ul/li//h4/a[@class='series']")
        trending_animes = [element.text for element in trending_elements]

        trending_text.config(state=tk.NORMAL)
        trending_text.delete('1.0', tk.END)
        trending_text.insert(tk.END, "\n".join(trending_animes))
        trending_text.config(state=tk.DISABLED)
    except Exception as e:
        print("Error updating trending animes:", e)

def update_popular_animes():
    try:
        # driver.get("https://animension.to/")  # Or the relevant URL for your site
        popular_elements = driver.find_elements(By.XPATH, "//div[@id='sidebar']/div[2]//ul/li//h4/a[@class='series']")
        popular_animes = [element.text for element in popular_elements]

        popular_text.config(state=tk.NORMAL)
        popular_text.delete('1.0', tk.END)
        popular_text.insert(tk.END, "\n".join(popular_animes))
        popular_text.config(state=tk.DISABLED)
    except Exception as e:
        print("Error updating popular animes:", e)

def extract_episodes_list():
    global initial_episode_count

    try:
        episode_number = 1

        # Create a popup window for the "Fetching data..." message
        fetching_popup = Toplevel(root)
        fetching_popup.title("Fetching Data")
        fetching_popup.geometry("300x100")

        # Calculate the center position of the screen
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - 300) // 2
        y = (screen_height - 100) // 2

        fetching_popup.geometry(f"300x100+{x}+{y}")

        fetching_label = tk.Label(fetching_popup, text="Fetching data...")
        fetching_label.pack(padx=20, pady=20)
        fetching_popup.focus_set()
        fetching_popup.grab_set()

        while True:
            try:
                driver.get(episode_list_url)
                time.sleep(2)

                episode_elements = driver.find_elements(By.XPATH, "//div[@id='anime_episodes']/ul//div[@class='sli-name']/a")

                if episode_number == 1 and initial_episode_count is None:
                    initial_episode_count = len(episode_elements)

                num_episodes = len(episode_elements)

                if num_episodes == 0 or episode_number > initial_episode_count:
                    break

                episode_element = episode_elements[num_episodes - episode_number]

                episode_title = episode_element.text
                print(f"Episode {episode_number}: {episode_title}")

                episode_element.click()
                time.sleep(2)

                vidcdn(episode_number)

                episode_number += 1

                # Update the message in the popup window
                fetching_label.config(text=f"Fetching data... (Episode {episode_number}/{initial_episode_count})")
                fetching_popup.update()

                # Close the popup when the iteration is finished
                if episode_number > initial_episode_count:
                    fetching_popup.destroy()
                    show_centered_popup_message("Videos are ready!")

            except Exception as e:
                print(f"An error occurred while processing Episode {episode_number}: {str(e)}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

def vidcdn(episode_number):
    try:
        vidcdn_link_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='VidCDN']"))
        )
        
        vidcdn_link = vidcdn_link_element.get_attribute('href')
        driver.get(vidcdn_link)
        extract_m3u8_full(driver, episode_number)

    except Exception as e:
        print(f"An error occurred in the vidcdn function for Episode {episode_number}: {str(e)}")

def extract_m3u8_full(driver, episode_number):
    try:
        m3u8_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[@class='current']/following-sibling::ul/li[1]"))
        )

        m3u8_raw = m3u8_element.get_attribute("data-value")

        m3u8_regex = r"(https?://.*?\.m3u8)"
        m3u8_match = re.search(m3u8_regex, m3u8_raw)

        if m3u8_match:
            m3u8_urls_dict[episode_number] = m3u8_match.group()

    except Exception as e:
        print(f"An error occurred in extract_m3u8 for Episode {episode_number}: {str(e)}")

def extract_m3u8(driver, episode_number):
    try:
        m3u8_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[@class='current']/following-sibling::ul/li[1]"))
        )

        m3u8_raw = m3u8_element.get_attribute("data-value")

        m3u8_regex = r"(https?://.*?\.m3u8)"
        m3u8_match = re.search(m3u8_regex, m3u8_raw)

        if m3u8_match:
            m3u8_urls_dict[episode_number] = m3u8_match.group()

    except Exception as e:
        print(f"An error occurred in extract_m3u8 for Episode {episode_number}: {str(e)}")

# Create a function to display a popup message centered on the screen
def show_centered_popup_message(message):
    popup = Toplevel(root)
    popup.title("Message")
    popup.geometry("300x100")

    # Calculate the center position of the screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 300) // 2
    y = (screen_height - 100) // 2

    popup.geometry(f"300x100+{x}+{y}")

    label = tk.Label(popup, text=message)
    label.pack(padx=20, pady=20)
    popup.focus_set()
    popup.grab_set()

    # Automatically close the popup after 3 seconds (adjust as needed)
    popup.after(3000, popup.destroy)

# Function to play video using mpv
def play_video():
    episode_number = txt_full_choice.get()
    if episode_number.isdigit():
        episode_number = int(episode_number)
        if episode_number in m3u8_urls_dict:
            m3u8_url = m3u8_urls_dict[episode_number]
            subprocess.run(["mpv", m3u8_url])
        else:
            show_centered_popup_message("Video not found for the selected episode.")
    else:
        show_centered_popup_message("Please enter a valid episode number.")

# Tkinter UI setup
root = tk.Tk()
root.title("Anime Scraper")

# Get screen width and height
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# Set window size as a percentage of screen size (e.g., 70% of the screen size)
window_width = int(screen_width * 0.4)
window_height = int(screen_height * 0.5)

# Calculate x and y coordinates for the Tk root window to be centered
x = int((screen_width / 2) - (window_width / 2))
y = int((screen_height / 2) - (window_height / 2))

# Set the geometry of the tk root window and center it
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

sub_var = tk.IntVar()
dub_var = tk.IntVar()

# Create main content frame (left side)
main_frame = tk.Frame(root)
main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Search frame within main content
search_frame = tk.Frame(main_frame)
search_frame.pack()

# Search-related widgets
search_label = tk.Label(search_frame, text="Search anime:")
search_label.pack(side=tk.LEFT)

search_entry = tk.Entry(search_frame, width=50)
search_entry.pack(side=tk.LEFT)
search_entry.focus_set()

search_button = tk.Button(search_frame, text="Search", command=lambda: threading.Thread(target=search_anime, args=(search_entry.get(), results_text, episodes_text, m3u8_entry)).start())
search_button.pack(side=tk.LEFT)

sub_checkbutton = tk.Checkbutton(search_frame, text="Sub", variable=sub_var, command=lambda: checkbutton_callback('sub'))
sub_checkbutton.pack(side=tk.LEFT)

dub_checkbutton = tk.Checkbutton(search_frame, text="Dub", variable=dub_var, command=lambda: checkbutton_callback('dub'))
dub_checkbutton.pack(side=tk.LEFT)

# Results text area
results_text = scrolledtext.ScrolledText(main_frame, height=10, width=80)
results_text.pack()
results_text.config(state=tk.DISABLED)

# Anime choice widgets
choice_label = tk.Label(main_frame, text="Your anime choice (choose from the list ex. 3):")
choice_label.pack()

choice_entry = tk.Entry(main_frame, width=20)
choice_entry.pack()

submit_choice_button = tk.Button(main_frame, text="Fetch Episodes", command=fetch_episodes)
submit_choice_button.pack()

# Episodes text area
episodes_text = scrolledtext.ScrolledText(main_frame, height=10, width=80)
episodes_text.pack()
episodes_text.config(state=tk.DISABLED)

# Episode entry and submit button
episode_label = tk.Label(main_frame, text="Enter your chosen episode:")
episode_label.pack()

episode_entry = tk.Entry(main_frame, width=20)
episode_entry.pack()

# Create a new frame for fetch buttons
fetch_frame = tk.Frame(main_frame)
fetch_frame.pack()
btn_fetch_vide = tk.Button(fetch_frame, text="Fetch Video", command=fetch_video)
btn_fetch_vide.pack(side=tk.LEFT, padx=5, pady=5)
btn_fetch_all_vids= tk.Button(fetch_frame, text="Fetch ALL Videos", command=extract_episodes_list)
btn_fetch_all_vids.pack(side=tk.LEFT, padx=5, pady=5)
m3u8_label = tk.Label(main_frame, text="M3U8:")
m3u8_label.pack()
# M3U8 URL display
m3u8_entry = tk.Entry(main_frame, width=80)
m3u8_entry.pack()
m3u8_entry.config(state='readonly')

# Create a new frame at the bottom for the buttons
bottom_frame = tk.Frame(main_frame)
bottom_frame.pack()
play_mpv_button = tk.Button(bottom_frame, text="Play on MPV", command=play_mpv)
play_mpv_button.pack(side=tk.LEFT, padx=5, pady=5)
select_another_episode_button = tk.Button(bottom_frame, text="Select Another Episode", command=select_another_episode)
select_another_episode_button.pack(side=tk.LEFT, padx=5, pady=5)
close_button = tk.Button(bottom_frame, text="Close", command=root.destroy)
close_button.pack(side=tk.LEFT, padx=5, pady=5)

# Right side frame for Trending and Popular animes
right_frame = tk.Frame(root)
right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
# Trending animes frame
trending_frame = tk.LabelFrame(right_frame, text="Trending")
trending_frame.pack(fill=tk.BOTH, expand=True)
trending_text = tk.Text(trending_frame, height=15, state='disabled')
trending_text.pack(fill=tk.BOTH, expand=True)
# Popular animes frame
popular_frame = tk.LabelFrame(right_frame, text="Popular")
popular_frame.pack(fill=tk.BOTH, expand=True)
popular_text = tk.Text(popular_frame, height=15, state='disabled')
popular_text.pack(fill=tk.BOTH, expand=True)


# Add Entry and Button for playing the video
full_choice_frame = tk.Frame(main_frame)
full_choice_frame.pack()
txt_full_choice = tk.Entry(full_choice_frame, width=10)
txt_full_choice.pack(side=tk.LEFT)
btnPlay = tk.Button(full_choice_frame, text="Play video", command=play_video)
btnPlay.pack(side=tk.LEFT, padx=5, pady=5)

# Load initial website and update lists of animes
load_initial_website()
update_trending_animes()
update_popular_animes()
# Start the Tkinter event loop
root.mainloop()
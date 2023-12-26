import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import subprocess
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import platform

# Initialize WebDriver
chromedriver_path = r"C:\Users\mewtc\coding\python\scraping\chromedriver.exe"
chrome_options = Options()
# chrome_options.add_argument("--headless")
service = Service(executable_path=chromedriver_path, log_path=os.devnull)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Global variable to store the episode list URL
episode_list_url = None
search_url = None  # New global variable to store the search URL

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
    
    threading.Thread(target=run_scraper, args=(search_entry.get(), results_text, episodes_text, m3u8_entry, filter_option)).start()

def run_scraper(search_term, results_text, episodes_text, m3u8_entry, filter_option=None):
    try:
        driver.get("https://animension.to/")

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

# Rest of the existing functions...
def fetch_episodes():
    global episode_list_url
    choice = root.choice.get()
    if not choice.isdigit() or int(choice) - 1 not in range(len(root.title_elements)):
        results_text.config(state=tk.NORMAL)
        results_text.insert(tk.END, "Invalid choice. Please enter a valid number.\n")
        results_text.config(state=tk.DISABLED)
        return

    selected_title = root.title_elements[int(choice) - 1]
    selected_title.click()

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

def select_another_episode():
    if episode_list_url:
        driver.get(episode_list_url)
        fetch_episodes()

def scrape_m3u8(episode_number):
    try:
        episode_link = root.episode_dict[episode_number]
        episode_link.click()

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
            root.m3u8_entry.config(state=tk.DISABLED)
            select_another_episode_button.config(state=tk.NORMAL)
        else:
            root.m3u8_entry.config(state=tk.NORMAL)
            root.m3u8_entry.delete(0, tk.END)
            root.m3u8_entry.insert(0, "No m3u8 link found in the URL.")
            root.m3u8_entry.config(state=tk.DISABLED)
            select_another_episode_button.config(state=tk.NORMAL)
    except Exception as e:
        root.m3u8_entry.config(state=tk.NORMAL)
        root.m3u8_entry.delete(0, tk.END)
        root.m3u8_entry.insert(0, f"Error: {str(e)}")
        root.m3u8_entry.config(state=tk.DISABLED)
        select_another_episode_button.config(state=tk.NORMAL)

def play_episode():
    episode_number = root.episode_choice.get()
    if not episode_number.isdigit() or int(episode_number) not in range(1, len(root.episode_dict) + 1):
        episodes_text.config(state=tk.NORMAL)
        episodes_text.insert(tk.END, "Invalid episode. Please enter a valid number.\n")
        episodes_text.config(state=tk.DISABLED)
        return

    root.m3u8_entry.config(state=tk.NORMAL)
    root.m3u8_entry.delete(0, tk.END)
    root.m3u8_entry.insert(0, "Fetching data...")
    root.m3u8_entry.config(state=tk.DISABLED)

    threading.Thread(target=scrape_m3u8, args=(episode_number,)).start()

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

# Tkinter UI setup
root = tk.Tk()
root.title("Anime Scraper")

# After initializing the main Tk window, you can safely create Tkinter variables.
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

search_button = tk.Button(search_frame, text="Search", command=lambda: threading.Thread(target=run_scraper, args=(search_entry.get(), results_text, episodes_text, m3u8_entry)).start())
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

submit_choice_button = tk.Button(main_frame, text="Submit Choice", command=fetch_episodes)
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

submit_episode_button = tk.Button(main_frame, text="Submit Episode", command=play_episode)
submit_episode_button.pack()

# M3U8 URL display
m3u8_label = tk.Label(main_frame, text="M3U8:")
m3u8_label.pack()

m3u8_entry = tk.Entry(main_frame, width=80)
m3u8_entry.pack()
m3u8_entry.config(state='readonly')

# MPV play button
play_mpv_button = tk.Button(main_frame, text="Play on MPV", command=play_mpv)
play_mpv_button.pack()

# Button to select another episode
select_another_episode_button = tk.Button(main_frame, text="Select Another Episode", state=tk.DISABLED, command=select_another_episode)
select_another_episode_button.pack()

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

# Load initial website and update lists of animes
load_initial_website()
update_trending_animes()
update_popular_animes()
# Start the Tkinter event loop
root.mainloop()
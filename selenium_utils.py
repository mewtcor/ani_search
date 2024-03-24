from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys

class SeleniumUtils:
    @staticmethod
    def wait_for_element(driver, by, value, timeout=10, wait_type='visible'):
        if wait_type == 'visible':
            condition = EC.visibility_of_element_located((by, value))
        elif wait_type == 'present':
            condition = EC.presence_of_element_located((by, value))
        else:
            raise ValueError("Invalid wait_type specified. Use 'visible' or 'present'.")
        return WebDriverWait(driver, timeout).until(condition)

    def set_video_output(self):
        """Set the video output to the video frame based on the operating system."""
        if sys.platform.startswith('linux'):  # for Linux using the X Server
            self.player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":  # for Windows
            self.player.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":  # for MacOS
            self.player.set_nsobject(int(self.video_frame.winId()))
            
    def play_video(self):
        """Play the video."""
        self.player.play()

    def pause_video(self):
        """Pause the video."""
        self.player.pause()

    def stop_video(self):
        """Stop the video."""
        self.player.stop()

    def maximize_video(self):
        """Maximize the video player window."""
        self.showFullScreen()

    def minimize_video(self):
        """Minimize the video player window."""
        self.showNormal()


from locust import User, between, task
import os
import socket
import subprocess
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

class CookielessEmbedDashboardUser(User):
    abstract = True
    wait_time = between(3600, 3600)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.port = get_free_port()
        self.host = f"http://127.0.0.1:{self.port}"
        self.debug = getattr(self, 'debug', False)

        server_path = os.path.join(
            os.path.dirname(__file__),
            "embed_cookieless_dashboard",
            "embed_server.py"
        )
        
        server_cmd = [sys.executable, server_path, str(self.port)]
        if self.debug:
            server_cmd.append("--debug")

        self.server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--v=1")

        chrome_options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_settings.cookies": 0,
                "profile.cookie_controls_mode": 0,
            },
        )
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        self.driver = webdriver.Chrome(options=chrome_options)

    def on_start(self):
        self.driver.get(self.host)
        try:
            print("Waiting up to 30 seconds for embed iframe to be present...")
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, "looker-embed"))
            )
            print("Embed iframe is present. Waiting 10 seconds for handshake to complete...")
            time.sleep(10)
        except Exception as e:
            print(f"Error waiting for iframe or handshake: {e}")
        finally:
            print("Printing browser logs:")
            for entry in self.driver.get_log('browser'):
                print(entry)

    # def on_stop(self):
    #     self.driver.quit()
    #     self.server_process.terminate()
    #     self.server_process.wait()

    @task
    def do_nothing(self):
        pass
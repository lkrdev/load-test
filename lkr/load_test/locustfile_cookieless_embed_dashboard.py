from locust import User, between, task
import os
import socket
import subprocess
import sys
import time
import json
from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

class CookielessEmbedDashboardUser(User):
    abstract = True
    wait_time = between(1000, 2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.port = get_free_port()
        self.host = f"http://127.0.0.1:{self.port}"
        self.debug = getattr(self, 'debug', False)
        self.group_ids: List[str] = getattr(self, 'group_ids', [])
        self.external_group_id: str | None = getattr(self, 'external_group_id', None)
        self.dashboard: str = getattr(self, 'dashboard', "")
        self.models: List[str] = getattr(self, 'models', [])
        self.attributes: List[str] = getattr(self, 'attributes', [])
        self.first_name: str = getattr(self, 'first_name', 'Embed')

        server_path = os.path.join(
            os.path.dirname(__file__),
            "embed_cookieless_dashboard",
            "embed_server.py"
        )
        
        server_cmd = [sys.executable, server_path, str(self.port)]
        if self.debug:
            server_cmd.append("--debug")

        lEnv = os.environ.copy()
        lEnv["DASHBOARD_ID"] = self.dashboard
        lEnv["MODELS"] = ",".join(self.models)
        lEnv["GROUP_IDS"] = ",".join(self.group_ids)
        lEnv["ATTRIBUTES"] = json.dumps(self.attributes)
        lEnv["FIRST_NAME"] = self.first_name
        if self.external_group_id:
            lEnv["EXTERNAL_GROUP_ID"] = self.external_group_id
        
        # Fail fast in Python: set timeout for Looker SDK requests
        if "LOOKERSDK_TIMEOUT" not in lEnv:
            lEnv["LOOKERSDK_TIMEOUT"] = "10"

        self.server_process = subprocess.Popen(
            server_cmd, env=lEnv
        )

        # Wait for the server to be ready with 10 second timeout
        is_server_ready = False
        for _ in range(20): 
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    is_server_ready = True
                    break
            except (socket.timeout, ConnectionRefusedError):
                time.sleep(0.5)

        if not is_server_ready:
            self.server_process.terminate()
            self.server_process.wait()
            raise Exception("Embed server failed to start")

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--v=1")

        # Speed up page loading by not waiting for non-critical subresources (CSS, images, fonts)
        chrome_options.page_load_strategy = "eager"

        # In VPCSC, block everything except required hosts to trigger immediate failure
        # instead of waiting for a 60-second network timeout.
        looker_url = os.environ.get("LOOKERSDK_BASE_URL", "")
        looker_host = urlparse(looker_url).hostname
        
        rules = "MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1"
        if looker_host:
            rules += f", EXCLUDE {looker_host}"
            
        chrome_options.add_argument(f"--host-resolver-rules={rules}")

        chrome_options.add_experimental_option(
            "prefs",
            {
                "profile.cookie_controls_mode": 1, # 1 = Block third-party cookies
            },
        )
        if self.debug:
            chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        self.driver = webdriver.Chrome(options=chrome_options)

    def on_start(self):
        self.driver.get(self.host)
        try:
            # Waiting up to 2 seconds for embed iframe to be present...")
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.ID, "looker-embed"))
            )
            print("Embed iframe is present. Waiting 2 seconds for handshake to complete...")
            time.sleep(2)
        except Exception as e:
            print(f"Error waiting for iframe or handshake: {e}")
        finally:
            for entry in self.driver.get_log('browser'):
                print(entry)
    
    def on_stop(self):
        try:
            if hasattr(self, "driver") and self.driver:
                self.driver.quit()
        except BaseException as e:
            print(f"Notice: Exception during driver.quit(): {e}")
        finally:
            self.driver = None

        try:
            if hasattr(self, "server_process") and self.server_process:
                self.server_process.terminate()
                self.server_process.wait()
        except BaseException as e:
            print(f"Notice: Exception during server cleanup: {e}")
        finally:
            self.server_process = None

    @task
    def do_nothing(self):
        pass

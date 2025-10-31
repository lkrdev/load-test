import os
import urllib.parse
from typing import List, Optional
from uuid import uuid4
import requests
import looker_sdk
import structlog
from locust import User, between, task  # noqa
from looker_sdk import models40, error
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from lkr.load_test.embed_dashboard_observability.events import EventLogger
from lkr.load_test.utils import (
    MAX_SESSION_LENGTH,
    PERMISSIONS,
    format_attributes,
    get_user_id,
    now,
)

logger = structlog.get_logger(name="looker-embed-observability")

__all__ = ["DashboardUserObservability"]


class DashboardUserObservability(User):
    abstract = True
    wait_time = between(1000, 2000)
    cleanup_user: bool = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sdk = None
        self.user_id = get_user_id()
        self.attributes: List[str] = []
        self.dashboard: str = ""
        self.models: List[str] = []
        self.group_ids: List[str] = []
        self.external_group_id: str | None = None
        self.task_start_time = None
        self.completion_timeout = 120
        self.embed_domain = "http://localhost:3000"
        self.log_event_prefix = "looker-embed-observability"
        self.do_not_open_url = False
        self.debug: bool = False
        self.embed_as_me: bool = False
        self.embed_user_id: str = ""
    
    def _return_dashboard(self):
        return self.dashboard.split(',')[0]

    def get_sso_url(self):
        attributes = format_attributes(self.attributes)
        if not self.sdk:
            raise ValueError("SDK not initialized")
        sso_url = self.sdk.create_sso_embed_url(
            models40.EmbedSsoParams(
                first_name="Embed",
                last_name=self.user_id,
                external_user_id=self.user_id,
                external_group_id=self.external_group_id,
                session_length=MAX_SESSION_LENGTH,  # max seconds
                target_url=f"{os.environ.get('LOOKERSDK_BASE_URL')}/embed/dashboards/{self._return_dashboard()}?embed_domain={self.embed_domain}",
                permissions=PERMISSIONS,
                models=self.models,
                user_attributes=attributes,
                group_ids=self.group_ids or [],
                # embed_domain=self.embed_domain,
            )
        )
        return sso_url
    
    ### create_embed_url_as_me
    # logs in as an existing embed user (assumes they have already been created) and generates embed session
    # doesn't include sensitive info in url, in Looker Core can only work for embed user and Looker Credentials need to be from API SA
    ###
    def get_embed_url_as_me(self):
        if not self.sdk:
            raise ValueError("SDK not initialized")
        embed_user_token = self.sdk.login_user(user_id=self.embed_user_id).access_token
        
        target_url = (
            f"{os.environ.get('LOOKERSDK_BASE_URL')}/embed/dashboards/{self._return_dashboard()}"
            f"?embed_domain={self.embed_domain}"
        )
        
        payload = {
            "target_url": target_url,
            "session_length": MAX_SESSION_LENGTH,
            "force_logout_login": False,
        }
        
        headers = {
            "Authorization": f"Bearer {embed_user_token}",
            "Content-Type": "application/json"
        }
        
        try:
            embed_url_as_me = requests.post(f"{os.environ.get('LOOKERSDK_BASE_URL')}/api/4.0/embed/token_url/me", json=payload, headers=headers)
            print(embed_url_as_me)
            return embed_url_as_me.json()
        except error.SDKError as e:
            print(e.message)

    def on_start(self):
        # Initialize the SDK - make sure to set your environment variables
        self.sdk = looker_sdk.init40()

    # TODO: Causing greenlet issues
    # def on_stop(self):
    #     if self.cleanup_user and self.sdk and self.user_id:
    #         user = self.sdk.user_for_credential("embed", self.user_id)
    #         if user and user.id:
    #             self.sdk.delete_user(user.id)

    @task
    def open_embed_dashboard(self):
        task_id = str(uuid4())
        self.event_logger = EventLogger.initialize(
            user_id=self.user_id,
            dashboard=self._return_dashboard(),
            task_id=task_id,
            log_event_prefix=self.log_event_prefix,
        )
        self.task_start_time = now()

        self.event_logger.log_event("user_task_start")

        chrome_options = Options()
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--v=1")

        chrome_options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_settings.cookies": 1,
                "profile.cookie_controls_mode": 0,
            },
        )

        driver = webdriver.Chrome(options=chrome_options)

        self.event_logger.log_event("user_task_chromium_driver_loaded")

        if self.embed_as_me:
            sso_url = self.get_embed_url_as_me()
            print(sso_url)

            self.event_logger.log_event("user_task_embed_url_as_me_generated")
            # Open the local embed container with the SSO URL as a parameter
            embed_url_params = {
                "dashboard_id": self.dashboard,
                "user_id": self.user_id,
                "task_id": task_id,
                "task_start_time": self.task_start_time.isoformat(),
            }
            if self.debug:
                embed_url_params["debug"] = "true"

            embed_url = f"{self.embed_domain}/?{urllib.parse.urlencode(embed_url_params)}&iframe_url={sso_url['url']}"
        else: 
            sso_url = self.get_sso_url()

            self.event_logger.log_event("user_task_sso_url_generated")
            quoted_url = urllib.parse.quote(str(sso_url.url), safe="")
            # Open the local embed container with the SSO URL as a parameter
            embed_url_params = {
                "dashboard_id": self.dashboard,
                "user_id": self.user_id,
                "task_id": task_id,
                "task_start_time": self.task_start_time.isoformat(),
            }
            if self.debug:
                embed_url_params["debug"] = "true"

            embed_url = f"{self.embed_domain}/?{urllib.parse.urlencode(embed_url_params)}&iframe_url={quoted_url}"

        if not self.do_not_open_url:
            try:
                driver.get(embed_url)
                self.event_logger.log_event(
                    "user_task_embed_chromium_get", embed_url=embed_url
                )
            except Exception as e:
                self.event_logger.log_event(
                    "user_task_embed_chromium_get_error",
                    embed_url=embed_url,
                    error=str(e),
                )
        else:
            self.event_logger.log_event(
                "looker_embed_task_not_opening_url",
                embed_url=sso_url['url'] if isinstance(sso_url,dict) else sso_url.url,
                observability_url=embed_url,
            )
            return

        # Wait for the completion indicator to appear (with a timeout)
        try:
            WebDriverWait(driver, self.completion_timeout).until(
                EC.presence_of_element_located((By.ID, "completion-indicator"))
            )

            # Log completion
            self.event_logger.log_event("looker_embed_task_complete")

        except TimeoutException:
            self.event_logger.log_event(
                "looker_embed_task_timeout",
                timeout=self.completion_timeout,
                error="Timeout waiting for completion indicator",
            )
        except Exception as e:
            self.event_logger.log_event("looker_embed_task_error", error=str(e))
        finally:
            if driver:
                if self.debug:
                    try:
                        console_logs = driver.get_log("browser")
                        self.event_logger.log_event(
                            "user_task_browser_logs",
                            browser_logs=console_logs,
                        )
                    except Exception as e:
                        self.event_logger.log_event(
                            "user_task_browser_logs_error", error=str(e)
                        )
                    try:
                        performance_logs = driver.get_log("performance")
                        self.event_logger.log_event(
                            "user_task_performance_logs",
                            performance_logs=performance_logs,
                        )
                    except Exception as e:
                        self.event_logger.log_event(
                            "user_task_performance_logs_error", error=str(e)
                        )
                driver.quit()

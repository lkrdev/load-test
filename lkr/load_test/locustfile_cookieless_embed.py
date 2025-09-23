from locust import User, between, task
from typing import List
import os
import looker_sdk
from looker_sdk import models40
from lkr.load_test.utils import (
    MAX_SESSION_LENGTH,
    PERMISSIONS,
    format_attributes,
    get_user_id,
)

class CookielessEmbedUser(User):
    abstract = True
    wait_time = between(1000, 2000)
    host = os.environ.get("LOOKERSDK_BASE_URL")
    abstract = True  # This is a base class
    cleanup_user: bool = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sdk = looker_sdk.init40()
        self.session = None
        self.user_id = get_user_id()
        self.attributes: List[str] = []
        self.group_ids: List[str] = []
        self.external_group_id: str | None = None
        self.models: List[str] = []



    def on_start(self):
        attributes = format_attributes(self.attributes)
        
        acquireSession = models40.EmbedCookielessSessionAcquire(
            first_name="Cookieless Embed",
            last_name=self.user_id,
            external_user_id=self.user_id,
            session_length=MAX_SESSION_LENGTH,
            permissions=PERMISSIONS,
            models=["basic_ecomm"],
            user_attributes=attributes,
            group_ids=self.group_ids or [],
            external_group_id=self.external_group_id,
            # session_reference_token
        )

        try:
            response = self.sdk.acquire_embed_cookieless_session(
                body=acquireSession
            )
            self.session = response
        except Exception as e:
            # This will be caught by locust and reported as a failure
            raise e


    @task
    def refresh_tokens(self):
        if self.session:
            try:
                response = self.sdk.generate_tokens_for_cookieless_session(
                    body={
                        "session_reference_token": self.session.session_reference_token,
                        "navigation_token": self.session.navigation_token,
                        "api_token": self.session.api_token
                    }
                )
                self.session = response
            except Exception as e:
                # This will be caught by locust and reported as a failure
                raise e
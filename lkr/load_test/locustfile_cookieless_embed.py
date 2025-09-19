from locust import User, between, task
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
    wait_time = between(1, 2)
    host = os.environ.get("LOOKERSDK_BASE_URL")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dashboard = "1"
        self.sdk = looker_sdk.init40()
        self.session = None
        self.user_id = get_user_id()


    def on_start(self):
        # attributes = format_attributes(["locale:en_US"])
        
        acquireSession = models40.EmbedCookielessSessionAcquire(
            first_name="Cookieless Embed",
            last_name=self.user_id,
            external_user_id=self.user_id,
            session_length=MAX_SESSION_LENGTH,
            permissions=PERMISSIONS,
            models=["basic_ecomm"],
            # user_attributes=attributes,
            # group_ids=["5"],
            external_group_id="test_group_1"
            # embed_domain
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
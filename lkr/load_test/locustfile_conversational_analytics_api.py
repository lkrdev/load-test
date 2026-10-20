import datetime
import os
import random
from typing import List, Optional

import looker_sdk
from locust import User, between, task
from looker_sdk import models40
from looker_sdk.sdk.api40.methods import Looker40SDK
from structlog import get_logger

from lkr.load_test.utils import (
    MAX_SESSION_LENGTH,
    PERMISSIONS,
    extract_looker_user_id_from_token,
    format_attributes,
    get_user_id,
)

logger = get_logger(__name__)

class ConversationalAnalyticsApiUser(User):
    abstract = True
    wait_time = between(1, 5)
    host = os.environ.get("LOOKERSDK_BASE_URL")
    cleanup_user: bool = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sdk: Looker40SDK | None = None
        self.user_id = get_user_id()
        self.agent_id: Optional[str] = None
        self.models: List[str] = []
        self.explores: List[str] = []
        self.agent_prompt: Optional[str] = None
        self.questions: List[str] = ["What are the top 5 products by sales?"]
        self.continue_conversation: bool = False
        self.attributes: List[str] = []
        self.group_ids: List[str] = []
        self.external_group_id: str | None = None
        self.first_name: str = "Embed"
        self.conversation_id: Optional[str] = None

    def _init_sdk(self):
        sdk = looker_sdk.init40()
        attributes = format_attributes(self.attributes)
        embed_session = sdk.acquire_embed_cookieless_session(
            models40.EmbedCookielessSessionAcquire(
                first_name=self.first_name,
                last_name=self.user_id,
                external_user_id=self.user_id,
                external_group_id=self.external_group_id,
                session_length=MAX_SESSION_LENGTH,
                permissions=PERMISSIONS + ["chat_with_explore"],
                models=self.models,
                user_attributes=attributes,
                group_ids=self.group_ids,
            )
        )
        looker_user_id = extract_looker_user_id_from_token(embed_session)
        if not looker_user_id:
            embed_user = sdk.user_for_credential("embed", self.user_id)
            if not embed_user or not embed_user.id:
                raise Exception("Failed to create embed user")
            looker_user_id = int(embed_user.id)

        sdk.auth.login_user(looker_user_id)
        return sdk

    def _get_or_create_agent(self, sdk: Looker40SDK):
        if self.agent_id:
            return self.agent_id

        # Create a new agent
        sources = []
        for model in self.models:
            for explore in self.explores:
                sources.append(models40.Source(model=model, explore=explore))

        if not sources:
            # Fallback if no explores specified but models are
            for model in self.models:
                sources.append(models40.Source(model=model))

        write_agent = models40.WriteAgent(
            name=f"Load Test Agent {self.user_id}",
            description="Agent created for load testing",
            sources=sources,
            context=models40.Context(instructions=self.agent_prompt) if self.agent_prompt else None
        )
        agent = sdk.create_agent(body=write_agent)
        return agent.id

    def _create_conversation(self, sdk: Looker40SDK, agent_id: str):
        write_conversation = models40.WriteConversation(
            name=f"Load Test Conversation {self.user_id}",
            agent_id=agent_id
        )
        conversation = sdk.create_conversation(body=write_conversation)
        return conversation.id

    def on_start(self):
        self.sdk = self._init_sdk()
        self.agent_id = self._get_or_create_agent(self.sdk)
        if self.continue_conversation:
            self.conversation_id = self._create_conversation(self.sdk, self.agent_id)

    @task
    def chat(self):
        if not self.sdk or not self.agent_id:
            return

        question = random.choice(self.questions)

        cid = self.conversation_id
        if not cid:
            cid = self._create_conversation(self.sdk, self.agent_id)

        start_time = datetime.datetime.now()
        try:
            self.sdk.conversational_analytics_chat(
                body=models40.ConversationalAnalyticsChatRequest(
                    conversation_id=cid,
                    user_message=question
                )
            )
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info(
                "conversational_analytics_chat",
                question=question,
                duration=duration,
                conversation_id=cid,
                agent_id=self.agent_id
            )
        except Exception as e:
            logger.error("chat_failed", error=str(e), question=question, conversation_id=cid)

        if not self.continue_conversation:
            # If not continuing, we don't save the conversation_id for the next task
            # (In standard Looker, we might want to delete it too, but maybe not for load test)
            pass

import os
import random
import time
from typing import List
from uuid import uuid4

import looker_sdk
from locust import User, between, task
from looker_sdk import models40
from looker_sdk.sdk.api40.methods import Looker40SDK
import structlog

from lkr.load_test.embed_dashboard_observability.events import EventLogger
from lkr.load_test.utils import (
    MAX_SESSION_LENGTH,
    PERMISSIONS,
    extract_looker_user_id_from_token,
    format_attributes,
    get_user_id,
    now,
    ms_diff,
)

logger = structlog.get_logger(__name__)

__all__ = ["DashboardQueriesUser"]


class DashboardQueriesUser(User):
    """
    Locust user that extracts queries from specified dashboards and runs them.
    Supports both synchronous and asynchronous query execution.
    """
    abstract = True
    wait_time = between(1, 15)
    host = os.environ.get("LOOKERSDK_BASE_URL")
    cleanup_user: bool = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sdk: Looker40SDK | None = None
        self.user_id = get_user_id()
        self.dashboard_ids: List[str] = []
        self.models: List[str] = []
        self.queries: List[str] = []
        self.result_format: str = "json_bi"
        self.query_async: bool = False
        self.attributes: List[str] = []
        self.async_bail_out: int = 120
        self.sticky_sessions: bool = False
        self.group_ids: List[str] = []
        self.external_group_id: str | None = None
        self.log_event_prefix: str = "looker-dashboard-queries"
        self.first_name: str = "Embed"

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
                permissions=PERMISSIONS,
                models=self.models,
                user_attributes=attributes,
                group_ids=self.group_ids or [],
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

    def _get_queries_from_dashboards(self, sdk: Looker40SDK):
        queries = set()
        for db_id in self.dashboard_ids:
            try:
                dashboard = sdk.dashboard(db_id)
                if dashboard.dashboard_elements:
                    for element in dashboard.dashboard_elements:
                        if element.query_id:
                            queries.add(str(element.query_id))
                        elif element.merge_result_id:
                            merge_query = sdk.merge_query(element.merge_result_id)
                            if merge_query.source_queries:
                                for q in merge_query.source_queries:
                                    if q and q.query_id:
                                        queries.add(str(q.query_id))
            except Exception as e:
                logger.error("Failed to get dashboard metadata", dashboard_id=db_id, error=str(e))
        return list(queries)

    def on_start(self):
        if self.sticky_sessions:
            self.sdk = self._init_sdk()
            self.queries = self._get_queries_from_dashboards(self.sdk)

    @task
    def run_dashboard_query(self):
        task_id = str(uuid4())
        db_display = ",".join(self.dashboard_ids) if self.dashboard_ids else "unknown"
        
        event_logger = EventLogger.initialize(
            user_id=self.user_id,
            dashboard=db_display,
            task_id=task_id,
            log_event_prefix=self.log_event_prefix,
        )
        
        event_logger.log_event("task_start")
        
        if not self.sdk:
            try:
                sdk = self._init_sdk()
                event_logger.log_event("sdk_initialized")
                queries = self._get_queries_from_dashboards(sdk)
                event_logger.log_event("metadata_fetched", query_count=len(queries))
            except Exception as e:
                event_logger.log_event("sdk_init_error", error=str(e))
                return
        else:
            sdk = self.sdk
            queries = self.queries
            
        if not queries:
            event_logger.log_event("no_queries_found")
            return
            
        query = random.choice(queries)
        event_logger.log_event("query_selected", query_id=query)
        
        start_time = now()
        
        try:
            if self.query_async:
                event_logger.log_event("run_query_async_start", query_id=query)
                
                if hasattr(models40, "ResultFormat"):
                    try:
                        result_format = models40.ResultFormat(self.result_format)
                    except Exception:
                        raise Exception(f"Invalid result_format: {self.result_format}")
                else:
                    raise Exception("models40.ResultFormat not available")
                    
                query_task = sdk.create_query_task(
                    models40.WriteCreateQueryTask(
                        query_id=int(query),
                        result_format=result_format,
                    ),
                    cache=False,
                )
                
                if not query_task or not getattr(query_task, "id", None):
                    raise Exception("Failed to create query task")
                    
                event_logger.log_event("query_task_created", task_id=query_task.id)
                
                for _ in range(self.async_bail_out):
                    status = sdk.query_task_results(query_task.id)
                    if isinstance(status, dict):
                        if "rows" in status:
                            break
                        errors = status.get("errors")
                        if errors is not None:
                            raise Exception(str(errors))
                    elif hasattr(status, "status") and status.status == "complete":
                        break
                    time.sleep(1)
                    
                event_logger.log_event("run_query_async_complete", query_id=query)
            else:
                event_logger.log_event("run_query_sync_start", query_id=query)
                sdk.run_query(query, result_format=self.result_format, cache=False)
                event_logger.log_event("run_query_sync_complete", query_id=query)
                
        except Exception as e:
            event_logger.log_event("query_error", error=str(e))
            
        event_logger.log_event("task_complete", duration_ms=ms_diff(start_time))

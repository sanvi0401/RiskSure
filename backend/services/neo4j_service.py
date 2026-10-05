import os
from typing import Any, Dict, List


class Neo4jService:
    def __init__(self):
        self.enabled = False
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        if self.uri and self.username and self.password:
            try:
                import neo4j  # noqa: F401
                self.enabled = True
            except Exception:
                self.enabled = False

    def is_enabled(self) -> bool:
        return self.enabled

    def sync_application(self, app_data: Dict[str, Any]):
        if not self.enabled:
            return {"status": "mocked", "message": "Neo4j not configured; skipping actual graph sync."}
        return {"status": "synced"}

    def get_graph_summary(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"nodes": 0, "relationships": 0, "status": "mocked"}
        return {"nodes": 0, "relationships": 0, "status": "empty"}

    def find_related_applications(self, application_id: int) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        return []


neo4j_service = Neo4jService()

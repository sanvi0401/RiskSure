"""Provider contracts and Neo4j visibility regression coverage."""
from contextlib import nullcontext
from types import SimpleNamespace

import integrations


class Node(dict):
    def __init__(self, label, identifier):
        super().__init__(id=identifier)
        self.labels = {label}


def test_neo4j_scoped_read_preserves_direction_and_excludes_peer_case(monkeypatch):
    application = Node("Application", 1)
    customer = Node("Customer", 7)
    peer = Node("Application", 2)
    submitted = SimpleNamespace(type="SUBMITTED", start_node=customer, end_node=application)
    peer_submitted = SimpleNamespace(type="SUBMITTED", start_node=customer, end_node=peer)
    session = SimpleNamespace(run=lambda *args, **kwargs: [{
        "a": application, "n1": customer, "r1": submitted, "n2": peer, "r2": peer_submitted,
    }])
    driver = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(integrations, "neo4j_driver", lambda: driver)
    monkeypatch.setattr(integrations, "_neo4j_session", lambda driver: nullcontext(session))
    graph = integrations.neo4j_application_graph(1, {"application-1", "customer-7"})
    assert {node["id"] for node in graph["nodes"]} == {"application-1", "customer-7"}
    assert graph["edges"] == [{"source": "customer-7", "target": "application-1", "relationship": "submitted"}]


def test_huggingface_chat_contract(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "test-provider-token")
    monkeypatch.setenv("HUGGINGFACE_MODEL", "configured-model")
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "choices": [{"message": {"content": '{"summary":"Supplied evidence only"}'}}],
        })

    monkeypatch.setattr(integrations.requests, "post", post)
    assert integrations.hf_request("Evidence", max_tokens=100) == '{"summary":"Supplied evidence only"}'
    assert captured["url"] == "https://router.huggingface.co/v1/chat/completions"
    assert captured["json"]["messages"] == [{"role": "user", "content": "Evidence"}]
    assert captured["json"]["model"] == "configured-model"

"""Builds a communication graph (nodes = phone numbers/handles, edges = calls+messages) for a case."""

from collections import defaultdict
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.call import Call
from app.models.contact import Contact
from app.models.message import Message


@dataclass
class GraphNode:
    id: str
    label: str
    call_count: int = 0
    message_count: int = 0


@dataclass
class GraphEdge:
    source: str
    target: str
    weight: int = 0


@dataclass
class EntityGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


def build(session: Session, case_id: int) -> EntityGraph:
    contacts = session.exec(select(Contact).where(Contact.case_id == case_id)).all()
    name_by_number = {c.phone_number: c.name for c in contacts if c.name}

    calls = session.exec(select(Call).where(Call.case_id == case_id)).all()
    messages = session.exec(select(Message).where(Message.case_id == case_id)).all()

    node_calls: dict[str, int] = defaultdict(int)
    node_messages: dict[str, int] = defaultdict(int)
    edge_weights: dict[tuple[str, str], int] = defaultdict(int)

    device_owner = "device_owner"
    node_calls[device_owner] = 0

    for call in calls:
        node_calls[call.number] += 1
        key = tuple(sorted((device_owner, call.number)))
        edge_weights[key] += 1

    for msg in messages:
        node_messages[msg.sender] += 1
        node_messages[msg.recipient] += 1
        key = tuple(sorted((msg.sender, msg.recipient)))
        edge_weights[key] += 1

    all_ids = set(node_calls) | set(node_messages)
    nodes = [
        GraphNode(
            id=node_id,
            label=name_by_number.get(node_id, "You" if node_id == device_owner else node_id),
            call_count=node_calls.get(node_id, 0),
            message_count=node_messages.get(node_id, 0),
        )
        for node_id in all_ids
    ]
    edges = [GraphEdge(source=s, target=t, weight=w) for (s, t), w in edge_weights.items()]

    return EntityGraph(nodes=nodes, edges=edges)

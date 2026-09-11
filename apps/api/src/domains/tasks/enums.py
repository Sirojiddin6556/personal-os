"""Enumerations for the Tasks domain."""

from enum import Enum


class TaskStatus(str, Enum):
    INBOX = "inbox"
    TODO = "todo"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

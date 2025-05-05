"""
Data models for InfiniteMemoryMCP.

This module defines the data models and schema for the MongoDB collections
used in the InfiniteMemoryMCP system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# Type alias for MongoDB ObjectId
ObjectId = str


@dataclass
class MemoryBase:
    """Base class for all memory items."""
    id: Optional[ObjectId] = None
    timestamp: datetime = field(default_factory=datetime.now)
    scope: str = "Global"
    tags: List[str] = field(default_factory=list)


@dataclass
class ConversationMemory(MemoryBase):
    """
    Represents a conversation message in memory.
    
    Maps to documents in the conversation_history collection.
    """
    conversation_id: str = ""
    speaker: str = ""  # "user" or "assistant"
    text: str = ""
    embedding: Optional[List[float]] = None


@dataclass
class SummaryMemory(MemoryBase):
    """
    Represents a summary of conversation(s) or topic.
    
    Maps to documents in the summaries collection.
    """
    conversation_id: Optional[str] = None
    topic_id: Optional[str] = None
    summary_text: str = ""
    time_range: Optional[Dict[str, datetime]] = None
    message_refs: List[ObjectId] = field(default_factory=list)
    embedding: Optional[List[float]] = None


@dataclass
class UserProfileItem(MemoryBase):
    """
    Represents a user profile item or preference.
    
    Maps to documents in the user_profile collection.
    """
    user_id: str = "default_user"
    key: str = ""
    value: Any = None
    category: str = "facts"  # "facts", "preferences", "contacts", etc.


@dataclass
class MemoryIndexItem:
    """
    Represents an item in the memory index for semantic search.
    
    Maps to documents in the memory_index collection.
    """
    id: Optional[ObjectId] = None
    embedding: List[float] = field(default_factory=list)
    source_collection: str = ""  # e.g., "conversation_history" or "summaries"
    source_id: ObjectId = ""
    scope: str = "Global"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryScope:
    """
    Represents a memory scope.
    
    Maps to scope documents in the metadata_scopes collection.
    """
    id: Optional[ObjectId] = None
    type: str = "scope"
    scope_name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    active: bool = True
    related_keywords: List[str] = field(default_factory=list)
    parent_scope: Optional[str] = None


def dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert a dataclass instance to a dictionary suitable for MongoDB.
    
    Handles datetime conversion and nested dataclasses.
    
    Args:
        obj: The dataclass instance to convert
        
    Returns:
        A dictionary representation suitable for MongoDB insertion
    """
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for field in obj.__dataclass_fields__:
            value = getattr(obj, field)
            if field == "id":
                # Skip id if None, MongoDB will generate it
                if value is not None:
                    result["_id"] = value
            else:
                result[field] = dataclass_to_dict(value)
        return result
    elif isinstance(obj, datetime):
        return obj
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    else:
        return obj


def dict_to_dataclass(data: Dict[str, Any], cls: Any) -> Any:
    """
    Convert a MongoDB document to a dataclass instance.
    
    Args:
        data: The MongoDB document
        cls: The dataclass type to convert to
        
    Returns:
        An instance of the specified dataclass
    """
    # Convert MongoDB _id to id
    if "_id" in data:
        data["id"] = data.pop("_id")
    
    # Create a new instance of the dataclass
    kwargs = {}
    for field_name, field_value in data.items():
        kwargs[field_name] = field_value
    
    return cls(**kwargs) 
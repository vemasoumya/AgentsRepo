import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from agent_framework import HistoryProvider, Message


class CosmosDBHistoryProvider(HistoryProvider):
    """
    A history provider that stores conversation history in Azure Cosmos DB SQL API.
    """
    
    def __init__(
        self, 
        endpoint: str, 
        database_name: str = "AgentHistory",
        container_name: str = "Conversations",
        credential: Optional[Any] = None,
        source_id: str = "cosmos_history"
    ):
        """
        Initialize the Cosmos DB history provider.
        
        Args:
            endpoint: Cosmos DB account endpoint URL
            database_name: Name of the existing database
            container_name: Name of the existing container
            credential: Azure credential (if None, will use DefaultAzureCredential)
            source_id: Unique identifier for this provider instance
        """
        super().__init__(source_id)
        self.endpoint = endpoint
        self.database_name = database_name
        self.container_name = container_name
        self.credential = credential or DefaultAzureCredential()
        self._client = None
        self._database = None
        self._container = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure the Cosmos DB client and resources are initialized."""
        if self._initialized:
            return
            
        # Create the Cosmos client
        self._client = CosmosClient(
            url=self.endpoint,
            credential=self.credential
        )
        
        # Get reference to existing database
        self._database = self._client.get_database_client(self.database_name)
        
        # Get reference to existing container
        self._container = self._database.get_container_client(self.container_name)
        
        self._initialized = True

    async def get_messages(
        self, session_id: str | None, *, state: dict[str, Any] | None = None, **kwargs: Any
    ) -> list[Message]:
        """Retrieve stored messages for this session."""
        if not session_id:
            return []
            
        await self._ensure_initialized()
        
        try:
            response = await self._container.read_item(
                item=session_id,
                partition_key=session_id
            )
            
            messages = []
            for msg_data in response.get("messages", []):
                # Restore message with all preserved metadata
                msg = Message(role=msg_data["role"], contents=msg_data["content"])
                # Restore any additional metadata/properties
                for key, value in msg_data.items():
                    if key not in ['role', 'content', 'timestamp']:
                        setattr(msg, key, value)
                messages.append(msg)
            return messages
        except Exception:
            # Item not found or other error
            return []

    async def save_messages(
        self,
        session_id: str | None,
        messages: Sequence[Message],
        *,
        state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Persist messages for this session."""
        if not session_id or not messages:
            return
            
        await self._ensure_initialized()
        
        # Convert messages to serializable format - preserve all metadata
        message_data = []
        for msg in messages:
            msg_dict = {
                "role": msg.role,
                "content": msg.text,
                "timestamp": datetime.utcnow().isoformat()
            }
            # Preserve any additional metadata/properties from the original message
            if hasattr(msg, '__dict__'):
                for key, value in msg.__dict__.items():
                    if key not in ['role', 'contents'] and value is not None:
                        try:
                            # Only store serializable values
                            json.dumps(value)  # Test if serializable
                            msg_dict[key] = value
                        except:
                            pass  # Skip non-serializable attributes
            message_data.append(msg_dict)
        
        # Try to read existing item first
        try:
            existing_item = await self._container.read_item(
                item=session_id,
                partition_key=session_id
            )
            
            # Update existing messages (append new ones)
            existing_messages = existing_item.get("messages", [])
            existing_messages.extend(message_data)
            existing_item["messages"] = existing_messages
            existing_item["updated_at"] = datetime.utcnow().isoformat()
            
            # Replace the item
            await self._container.replace_item(
                item=existing_item["id"],
                body=existing_item
            )
            
        except Exception:
            # If item doesn't exist, create it
            history_item = {
                "id": session_id,
                "session_id": session_id,  # Partition key
                "messages": message_data,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            await self._container.create_item(body=history_item)
    
    
    async def close(self):
        """Close the Cosmos DB client."""
        if self._client:
            await self._client.close()
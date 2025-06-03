from adk.tools import Tool
from datetime import datetime, timezone # For timestamps

# Placeholder for actual Firestore client and operations
# from google.cloud import firestore

class FirestoreMemoryTool(Tool):
    """A tool to save and load conversation history to/from Firestore.
    This is a placeholder and uses an in-memory dict to simulate Firestore.
    """
    def __init__(self, name="FirestoreMemoryTool", description="Manages persistent conversation memory using Firestore (simulated)."):
        super().__init__(name=name, description=description)
        # self.db = firestore.Client() # Actual client
        self._simulated_firestore_db = {} # session_id -> session_document
        print(f"{self.name}: Initialized (simulated Firestore).")

    def _get_timestamp(self):
        return datetime.now(timezone.utc).isoformat()

    def save_turn(self, session_id: str, turn_data: dict) -> dict:
        if not session_id:
            return {"status": "error", "message": "session_id is required"}

        print(f"{self.name}: Saving turn for session_id='{session_id}'. Data keys: {list(turn_data.keys())}")

        if session_id not in self._simulated_firestore_db:
            self._simulated_firestore_db[session_id] = {
                "session_id": session_id,
                "created_at": self._get_timestamp(),
                "updated_at": self._get_timestamp(),
                "conversation_history": []
            }

        session_doc = self._simulated_firestore_db[session_id]

        # Add a turn_id
        turn_id = len(session_doc["conversation_history"]) + 1
        full_turn_data = {"turn_id": turn_id, "timestamp": self._get_timestamp(), **turn_data}

        session_doc["conversation_history"].append(full_turn_data)
        session_doc["updated_at"] = self._get_timestamp()

        # Simulate Firestore write
        # In real Firestore:
        # session_ref = self.db.collection("adk_agent_sessions").document(session_id)
        # session_ref.set(session_doc, merge=True) # Or update specific fields

        print(f"{self.name}: Turn {turn_id} saved for session {session_id}. History length: {len(session_doc['conversation_history'])}")
        return {"status": "success", "session_id": session_id, "turn_id": turn_id}

    def load_session_history(self, session_id: str, limit: int = 10) -> list:
        if not session_id:
            return []

        print(f"{self.name}: Loading history for session_id='{session_id}', limit={limit}")
        session_doc = self._simulated_firestore_db.get(session_id)

        if not session_doc or "conversation_history" not in session_doc:
            print(f"{self.name}: No history found for session {session_id}.")
            return []

        # In real Firestore:
        # session_ref = self.db.collection("adk_agent_sessions").document(session_id)
        # doc = session_ref.get()
        # if doc.exists:
        #    history = doc.to_dict().get("conversation_history", [])
        #    return history[-limit:]
        # else:
        #    return []

        history = session_doc["conversation_history"]
        loaded_history = history[-limit:]
        print(f"{self.name}: Loaded {len(loaded_history)} turns for session {session_id}.")
        return loaded_history

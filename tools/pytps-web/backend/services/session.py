"""
session.py - In-memory session state management.
Each browser tab gets a session_id with its own parameter state.
"""

import uuid
import time
from typing import Optional
import numpy as np


class SessionState:
    """Holds all analysis state for one user session."""

    def __init__(self, session_id: str, default_params: dict):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_active = time.time()

        # Analysis parameters (from defaults)
        self.params = dict(default_params)

        # Current state
        self.image_path: Optional[str] = None
        self.image_data: Optional[np.ndarray] = None
        self.spec_data: Optional[np.ndarray] = None
        self.noise_spec: Optional[np.ndarray] = None
        self.parabola: Optional[np.ndarray] = None
        self.cutoff_energy = 0
        self.is_8bit = False

        # Batch mode
        self.is_analysing = False
        self.batch_file_list: list = []
        self.batch_results: list = []

        # Display options
        self.show_parabola = False
        self.spec_cursor = 0.0
        self.cmap = 'partical'

    def touch(self):
        self.last_active = time.time()

    def is_expired(self, max_age_seconds=3600):
        return (time.time() - self.last_active) > max_age_seconds


class SessionManager:
    """Manages all active sessions."""

    def __init__(self, default_params: dict):
        self._sessions: dict[str, SessionState] = {}
        self._default_params = default_params

    def create_session(self) -> SessionState:
        session_id = str(uuid.uuid4())[:8]
        session = SessionState(session_id, self._default_params)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def get_or_create(self, session_id: Optional[str] = None) -> SessionState:
        if session_id and session_id in self._sessions:
            s = self._sessions[session_id]
            s.touch()
            return s
        # Create with the provided session_id (or generate one)
        sid = session_id or str(uuid.uuid4())[:8]
        session = SessionState(sid, self._default_params)
        self._sessions[sid] = session
        return session

    def remove_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def cleanup_expired(self, max_age_seconds=3600):
        expired = [sid for sid, s in self._sessions.items()
                   if s.is_expired(max_age_seconds)]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def active_count(self) -> int:
        return len(self._sessions)

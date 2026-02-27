"""会话管理器 - 简化版"""
import threading
from typing import List, Optional, Dict, Any
from collections import OrderedDict
from datetime import datetime
from dataclasses import dataclass, field

from config import Config


@dataclass
class Message:
    """对话消息"""
    role: str  # 'user' 或 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Session:
    """用户会话"""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    current_run_id: Optional[str] = None
    waiting_for_input: bool = False
    interrupt_context: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    # 用于恢复流程的同步保护
    resume_pending: bool = False
    last_interrupt_msg: Optional[str] = None

    def add_message(self, role: str, content: str):
        """添加消息（保留最近消息，避免单会话无限增长）"""
        self.messages.append(Message(role, content))
        if len(self.messages) > Config.MAX_MESSAGES_PER_SESSION:
            self.messages = self.messages[-Config.MAX_MESSAGES_PER_SESSION:]




class SessionStore:
    """Bounded in-memory session store with LRU eviction."""

    def __init__(self, max_sessions: int):
        self._sessions: "OrderedDict[str, Session]" = OrderedDict()
        self._max_sessions = max_sessions

    def add(self, session: Session):
        self._sessions[session.session_id] = session
        self._sessions.move_to_end(session.session_id)
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is not None:
            self._sessions.move_to_end(session_id)
        return session

    def remove(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def values(self) -> List[Session]:
        return list(self._sessions.values())


class SessionManager:
    """会话管理器 - 线程安全"""

    def __init__(self):
        self._sessions = SessionStore(max_sessions=Config.MAX_SESSIONS)
        self._lock = threading.Lock()
        self._counter = 0

    def create_session(self) -> Session:
        """创建会话"""
        with self._lock:
            self._counter += 1
            session_id = f"session_{self._counter}_{int(datetime.now().timestamp())}"
            session = Session(session_id=session_id)
            self._sessions.add(session)
            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        with self._lock:
            return self._sessions.get(session_id)

    def update_session_run_id(self, session_id: str, run_id: str):
        """更新run_id"""
        session = self.get_session(session_id)
        if session:
            session.current_run_id = run_id

    def set_waiting_state(self, session_id: str, waiting: bool, context: Optional[Dict] = None):
        """设置等待状态"""
        session = self.get_session(session_id)
        if session:
            session.waiting_for_input = waiting
            session.interrupt_context = context

    def get_all_sessions(self) -> List[Session]:
        """获取所有会话"""
        with self._lock:
            return self._sessions.values()

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        with self._lock:
            return self._sessions.remove(session_id)


# 全局实例
session_manager = SessionManager()

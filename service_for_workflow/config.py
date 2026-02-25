"""
配置文件
集中管理应用配置
"""


class Config:
    """应用配置类"""

    # Gradio配置
    GRADIO_SERVER_NAME = "0.0.0.0"
    GRADIO_SERVER_PORT = 7860
    GRADIO_SHARE = False
    GRADIO_SHOW_ERROR = True

    # 异步处理配置
    MAX_ASYNC_WORKERS = 10
    TASK_CLEANUP_INTERVAL_MINUTES = 30

    # 会话管理配置
    SESSION_MAX_AGE_HOURS = 24
    MAX_SESSIONS = 1000

    # 工作流配置
    WORKFLOW_TIMEOUT_SECONDS = 300  # 5分钟超时
    WORKFLOW_POLL_INTERVAL_SECONDS = 1  # 轮询间隔

    # 日志配置
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # UI配置
    CHATBOT_HEIGHT = 500
    MAX_MESSAGE_LENGTH = 5000
    REFRESH_BUTTON_ENABLED = True

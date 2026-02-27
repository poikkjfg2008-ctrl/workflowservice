"""
异步任务处理器 - 简化版
"""
import asyncio
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Optional, Callable

from workflow_adapter import getflowinfo
from config import Config


class AsyncProcessor:
    """异步处理器"""

    def __init__(self, max_workers: int = Config.MAX_ASYNC_WORKERS):
        self._tasks: "OrderedDict[str, Dict]" = OrderedDict()
        self._task_counter = 0
        self._lock = threading.Lock()
        self._loop = None
        self._loop_ready = threading.Event()
        self._poll_interval = Config.WORKFLOW_POLL_INTERVAL_SECONDS
        self._max_workers = max_workers
        self._task_semaphore: Optional[asyncio.Semaphore] = None
        self._start_event_loop()

    def _start_event_loop(self):
        """启动事件循环线程"""

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._task_semaphore = asyncio.Semaphore(self._max_workers)
            self._loop_ready.set()
            self._loop.run_forever()

        threading.Thread(target=run_loop, daemon=True).start()
        self._loop_ready.wait(timeout=3)

    async def _run_task(self, task_id: str, session_id: str, run_id: str, callback: Optional[Callable]):
        """运行异步任务 - 轮询工作流状态"""
        try:
            if self._task_semaphore is None:
                raise RuntimeError("Task semaphore not initialized")

            async with self._task_semaphore:
                print(f"[AsyncProcessor] 开始监控任务: {task_id}, run_id: {run_id}")

                # 轮询工作流状态，直到完成或中断
                while True:
                    try:
                        result = getflowinfo(run_id)
                        status = result.get('status', '')

                        print(f"[AsyncProcessor] 任务状态: {task_id}, run_id: {run_id}, status: {status}")

                        # 如果是最终状态（成功、失败、中断），停止轮询
                        if status in ['success', 'fail', 'interrupted']:
                            print(f"[AsyncProcessor] 任务完成: {task_id}, 状态: {status}")

                            # 更新任务状态
                            with self._lock:
                                if task_id in self._tasks:
                                    self._tasks[task_id]['completed'] = True
                                    self._tasks[task_id]['result'] = result

                            # 执行回调
                            if callback:
                                await callback(session_id, result)
                            break

                        # 如果是 processing 状态，继续轮询
                        if status == 'processing':
                            # Processing 状态不需要回调，前端通过轮询获取进度
                            await asyncio.sleep(self._poll_interval)
                            continue

                        # 未知状态
                        print(f"[AsyncProcessor] 未知状态: {status}")
                        await asyncio.sleep(self._poll_interval)

                    except ValueError as e:
                        # run_id 不存在
                        print(f"[AsyncProcessor] 任务异常: {task_id}, 错误: {str(e)}")
                        error_result = {
                            "runId": run_id,
                            "status": "fail",
                            "error": f"工作流不存在: {str(e)}",
                            "nodes": {},
                            "steps": [],
                            "costMs": 0,
                            "output": None
                        }
                        with self._lock:
                            if task_id in self._tasks:
                                self._tasks[task_id]['completed'] = True
                                self._tasks[task_id]['result'] = error_result
                        if callback:
                            await callback(session_id, error_result)
                        break

        except Exception as e:
            print(f"[AsyncProcessor] 任务异常: {task_id}, 错误: {str(e)}")
            error_result = {
                "runId": run_id,
                "status": "fail",
                "error": f"处理异常: {str(e)}",
                "nodes": {},
                "steps": [],
                "costMs": 0,
                "output": None
            }
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]['completed'] = True
                    self._tasks[task_id]['result'] = error_result

            if callback:
                await callback(session_id, error_result)

    def _trim_task_history(self):
        """限制任务历史，避免内存无限增长。"""
        while len(self._tasks) > Config.MAX_TASK_HISTORY:
            self._tasks.popitem(last=False)

    def submit_task(self, session_id: str, run_id: str, status_callback: Optional[Callable] = None) -> str:
        """提交异步任务"""
        with self._lock:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}_{int(datetime.now().timestamp())}"

            self._tasks[task_id] = {
                'task_id': task_id,
                'session_id': session_id,
                'run_id': run_id,
                'completed': False,
                'result': None
            }
            self._trim_task_history()

        # 在事件循环中运行任务
        asyncio.run_coroutine_threadsafe(
            self._run_task(task_id, session_id, run_id, status_callback),
            self._loop
        )

        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_active_tasks_count(self) -> int:
        """获取活跃任务数"""
        with self._lock:
            return sum(1 for t in self._tasks.values() if not t['completed'])


# 全局实例
async_processor = AsyncProcessor()

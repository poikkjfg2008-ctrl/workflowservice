# 工作流系统集成指南

本文档详细说明如何将实际的工作流服务集成到当前的Flask对话系统中。

## 📢 重要更新（最新版本）

系统已重构为使用**三个核心函数接口**，简化集成流程：

1. ✅ `runworkflow(user_input)` - 启动工作流
2. ✅ `getflowinfo(run_id)` - 查询工作流状态
3. ✅ `resumeflow(user_input, run_id)` - 恢复中断的工作流（**run_id保持不变**）

**关键修正：** 中断恢复逻辑已修复，现在使用 `resumeflow()` 函数保持原 run_id 不变，而不是创建新工作流。

## 目录

1. [三个核心函数](#三个核心函数)
2. [系统概述](#系统概述)
3. [集成步骤](#集成步骤)
4. [API接口规范](#api接口规范)
5. [测试指南](#测试指南)
6. [常见问题](#常见问题)

---

## 三个核心函数

### 1. runworkflow(user_input: str) -> str

启动新的工作流实例。

**参数：**
- `user_input`: 用户输入语句

**返回：**
- `run_id`: 工作流运行实例ID（25位数字字符串）

**示例：**
```python
from workflow_adapter import runworkflow

run_id = runworkflow("分析最近一个月的销售数据")
# 返回: "0000000000000000000000001"
```

---

### 2. getflowinfo(run_id: str) -> dict

查询工作流状态和信息。

**参数：**
- `run_id`: 工作流运行ID

**返回：**
```python
{
    'runId': str,                    # 工作流ID
    'status': str,                   # 状态: processing/interrupted/success/fail
    'nodes': {                       # 节点信息
        'node_id': {
            'input': {...},          # 节点输入
            'output': {...},         # 节点输出
            'status': str,           # 节点状态: pending/processing/success/interrupted/fail
            'costMs': int,           # 耗时（毫秒）
            'nodeType': str          # 节点类型: start/flow/condition/end
        }
    },
    'steps': [str],                  # 节点执行顺序
    'costMs': int,                   # 总耗时
    'output': Any,                   # 成功时的输出

    # 以下是可选字段
    'lastInterruptedNodeId': str,    # 中断节点ID（interrupted状态）
    'checkpointExpireTimestamp': int, # 检查点过期时间（interrupted状态）
    'msg': str,                      # 中断消息（interrupted状态）
    'error': str                     # 错误信息（fail状态）
}
```

**状态说明：**
- `processing`: 工作流正在执行
- `interrupted`: 工作流被中断，需要用户输入
- `success`: 工作流成功完成
- `fail`: 工作流执行失败

**示例：**
```python
from workflow_adapter import getflowinfo

info = getflowinfo("0000000000000000000000001")
print(info['status'])  # 'processing'
print(info['nodes'])   # 节点详情
```

---

### 3. resumeflow(user_input: str, run_id: str) -> None

恢复被中断的工作流。

**参数：**
- `user_input`: 用户针对中断信息的补充输入
- `run_id`: 被中断的工作流运行ID（**保持不变**）

**返回：**
- None（无返回值）

**⚠️ 重要：** 此函数不会创建新的 run_id，而是恢复原工作流！

**示例：**
```python
from workflow_adapter import resumeflow

# 工作流被中断，用户提供补充信息
resumeflow("按产品分析近30天的数据", "0000000000000000000000001")
# 工作流继续执行，run_id 保持不变
```

---

## 系统概述

### 当前架构

```
用户输入 → Flask API → Session Manager → Async Processor → Workflow Mock Service
                                  ↓                              ↓
                            Session Storage                模拟工作流执行
                                  ↓                              ↓
                            用户消息 ←─────────────── 状态轮询 ←─┘
```

### 核心组件

1. **flask_app.py** - Web服务器和API端点
2. **session_manager.py** - 会话管理（存储对话历史）
3. **async_processor.py** - 异步任务处理器
4. **workflow_mock.py** - 模拟工作流服务（**需要替换**）

---

## 代码审查报告

### ✅ 已确认的正确性

1. **workflow_mock.py**
   - ✅ run_id生成格式正确（25位数字）
   - ✅ 节点状态转换逻辑正确
   - ✅ 最终状态决定逻辑正确（基于run_id最后一位）
   - ✅ condition节点结构已修复

2. **flask_app.py**
   - ✅ workflow_callback正确处理所有4种状态
   - ✅ get_workflow_status正确返回节点信息
   - ✅ send_message正确处理中断后的输入（已修复）
   - ✅ 错误处理完善

3. **index.html**
   - ✅ 状态轮询逻辑正确
   - ✅ UI更新正确（processing/interrupted/success/fail）
   - ✅ 节点详情显示正确
   - ✅ 用户体验流畅

### 🔧 已修复的问题

1. **flask_app.py:215** - 移除了不存在的`restart_workflow`调用
2. **workflow_mock.py:228** - 修复了condition节点的input结构

### ✨ 用户体验优化

- Processing状态显示实时进度和节点详情
- Interrupted状态清晰提示需要补充的信息
- Success状态展示完整结果和可视化链接
- Fail状态提供明确的错误原因

---

## 实际工作流服务集成步骤

### 步骤1: 创建实际工作流服务适配器

创建新文件 `workflow_service.py`:

```python
"""
实际工作流服务适配器
"""
import requests
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class RealWorkflowService:
    """实际工作流服务客户端"""

    def __init__(self, base_url: str):
        """
        初始化工作流服务客户端

        Args:
            base_url: 实际工作流服务的基础URL
                     例如: "http://localhost:8080" 或 "https://workflow.yourcompany.com"
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = 300  # 5分钟超时

    def start_workflow(self, user_input: str) -> str:
        """
        启动工作流

        Args:
            user_input: 用户输入语句

        Returns:
            run_id: 工作流运行实例ID

        Raises:
            requests.RequestException: 网络请求失败
            ValueError: API返回错误
        """
        url = f"{self.base_url}/api/workflow/start"

        try:
            response = requests.post(
                url,
                json={"input": user_input},
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()

            # 假设实际API返回格式: {"run_id": "..."}
            run_id = data.get("run_id")
            if not run_id:
                raise ValueError(f"API未返回run_id: {data}")

            logger.info(f"[Workflow] 启动成功: {run_id}, 输入: {user_input}")
            return run_id

        except requests.RequestException as e:
            logger.error(f"[Workflow] 启动失败: {e}")
            raise

    def get_workflow_info(self, run_id: str) -> Dict[str, Any]:
        """
        获取工作流信息

        Args:
            run_id: 工作流运行实例ID

        Returns:
            工作流信息字典，格式:
            {
                'runId': str,
                'status': str,  # processing/interrupted/success/fail
                'nodes': Dict[str, NodeInfo],
                'steps': List[str],
                'costMs': int,
                'output': Any,
                # 如果是 interrupted 状态，还包含：
                'lastInterruptedNodeId': str,
                'checkpointExpireTimestamp': int,
                'msg': str
                # 如果是 fail 状态，还包含：
                'error': str
            }

        Raises:
            requests.RequestException: 网络请求失败
            ValueError: run_id不存在
        """
        url = f"{self.base_url}/api/workflow/{run_id}/info"

        try:
            response = requests.get(
                url,
                timeout=self.timeout
            )

            if response.status_code == 404:
                raise ValueError(f"Run ID {run_id} 不存在")

            response.raise_for_status()
            data = response.json()

            logger.debug(f"[Workflow] 查询状态: {run_id}, 状态: {data.get('status')}")
            return data

        except requests.RequestException as e:
            logger.error(f"[Workflow] 查询状态失败: {run_id}, 错误: {e}")
            raise


# 创建全局实例
# 从环境变量或配置文件读取实际工作流服务的URL
import os
WORKFLOW_SERVICE_URL = os.getenv(
    'WORKFLOW_SERVICE_URL',
    'http://localhost:8080'  # 默认值
)

workflow_service = RealWorkflowService(WORKFLOW_SERVICE_URL)
```

### 步骤2: 更新flask_app.py的导入

在 `flask_app.py` 的开头:

```python
# 将这行:
# from workflow_mock import workflow_service, WorkflowStatus

# 改为:
from workflow_service import workflow_service
```

**注意**: 实际服务不需要导入WorkflowStatus，因为我们直接使用字符串比较。

### 步骤3: 更新workflow_callback函数

在 `flask_app.py` 中，`workflow_callback` 函数已经支持实际的数据结构，无需修改。

但如果你需要添加额外的错误处理:

```python
async def workflow_callback(session_id: str, result: Dict[str, Any]):
    """工作流状态回调"""
    session = session_manager.get_session(session_id)
    if not session:
        logger.warning(f"[Callback] Session不存在: {session_id}")
        return

    status = result.get("status", "")

    try:
        # 原有的状态处理逻辑
        if status == "processing":
            # ... (保持不变)
        elif status == "interrupted":
            # ... (保持不变)
        elif status == "success":
            # ... (保持不变)
        elif status == "fail":
            # ... (保持不变)
        else:
            logger.warning(f"[Callback] 未知状态: {status}")

    except Exception as e:
        logger.error(f"[Callback] 处理失败: {e}", exc_info=True)
        session.add_message("assistant", f"处理工作流状态时出错: {str(e)}")
```

### 步骤4: 配置环境变量

创建 `.env` 文件或在启动脚本中设置:

```bash
export WORKFLOW_SERVICE_URL="http://your-workflow-service.com:8080"
```

或者直接修改 `workflow_service.py` 中的 `WORKFLOW_SERVICE_URL`。

### 步骤5: 测试集成

```bash
# 启动Flask应用
cd service_for_workflow
python3 flask_app.py

# 在另一个终端测试API
curl http://localhost:5000/api/session
curl -X POST http://localhost:5000/api/send -H "Content-Type: application/json" -d '{"message": "测试"}'
```

---

## API接口规范

### 实际工作流服务需要实现的API

#### 1. 启动工作流

**接口**: `POST /api/workflow/start`

**请求**:
```json
{
    "input": "用户输入语句"
}
```

**响应**:
```json
{
    "run_id": "0000000000000000000000001",
    "status": "processing"
}
```

#### 2. 查询工作流状态

**接口**: `GET /api/workflow/{run_id}/info`

**响应**:

##### Processing状态
```json
{
    "runId": "0000000000000000000000001",
    "status": "processing",
    "nodes": {
        "d12345678901234567890123": {
            "input": {"para1": "...", "para2": "..."},
            "output": {"para1": "...", "para2": "..."},
            "status": "success",
            "costMs": 150,
            "nodeType": "start"
        },
        "d12345678901234567890124": {
            "input": {"data": "..."},
            "output": null,
            "status": "processing",
            "costMs": 50,
            "nodeType": "flow"
        }
    },
    "steps": ["d12345678901234567890123", "d12345678901234567890124", "..."],
    "costMs": 200,
    "output": null
}
```

##### Interrupted状态
```json
{
    "runId": "0000000000000000000000001",
    "status": "interrupted",
    "nodes": {...},
    "steps": [...],
    "costMs": 5000,
    "output": null,
    "lastInterruptedNodeId": "d12345678901234567890124",
    "checkpointExpireTimestamp": 1771933135581,
    "msg": "需要更多信息：请提供数据范围和分析维度"
}
```

##### Success状态
```json
{
    "runId": "0000000000000000000000001",
    "status": "success",
    "nodes": {...},
    "steps": [...],
    "costMs": 7285,
    "output": {
        "summary": "分析完成！销售额增长了25%",
        "details": {
            "total_sales": "1,250,000",
            "growth_rate": "+25%"
        }
    }
}
```

##### Fail状态
```json
{
    "runId": "0000000000000000000000001",
    "status": "fail",
    "nodes": {...},
    "steps": [...],
    "costMs": 3000,
    "output": null,
    "error": "数据处理失败：连接数据库超时"
}
```

### 节点类型说明

- **start**: 开始节点
- **flow**: 流程节点
- **condition**: 条件节点
- **end**: 结束节点

### 节点状态说明

- **pending**: 等待执行
- **processing**: 正在执行
- **success**: 执行成功
- **interrupted**: 被中断
- **fail**: 执行失败

---

## 测试指南

### 单元测试

测试实际工作流服务的连接:

```python
# test_workflow_service.py
import requests
import time

def test_workflow_service():
    base_url = "http://your-workflow-service.com:8080"

    # 1. 启动工作流
    response = requests.post(
        f"{base_url}/api/workflow/start",
        json={"input": "分析销售数据"}
    )
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]
    print(f"✓ 工作流已启动: {run_id}")

    # 2. 轮询状态
    max_attempts = 10
    for i in range(max_attempts):
        response = requests.get(f"{base_url}/api/workflow/{run_id}/info")
        assert response.status_code == 200
        data = response.json()
        status = data["status"]
        print(f"✓ 第{i+1}次查询: {status}")

        if status in ["success", "fail", "interrupted"]:
            break

        time.sleep(2)

    print(f"✓ 最终状态: {status}")
```

### 集成测试

测试完整的Flask应用:

```bash
# 1. 启动Flask应用
python3 flask_app.py

# 2. 测试会话创建
curl http://localhost:5000/api/session

# 3. 发送消息
curl -X POST http://localhost:5000/api/send \
    -H "Content-Type: application/json" \
    -d '{"message": "分析最近一个月的销售数据"}'

# 4. 轮询工作流状态（将run_id替换为实际值）
curl http://localhost:5000/api/workflow/0000000000000000000000001/status

# 5. 如果中断，补充信息
curl -X POST http://localhost:5000/api/workflow/0000000000000000000000001/resume \
    -H "Content-Type: application/json" \
    -d '{"input": "按产品分组分析"}'
```

### 端到端测试

通过Web界面测试:

1. 打开浏览器访问 `http://localhost:5000`
2. 输入测试消息并发送
3. 观察进度条和节点详情
4. 等待工作流完成/中断/失败
5. 如果中断，补充信息继续

---

## 常见问题

### Q1: 实际工作流服务返回的数据格式不完全匹配怎么办？

**A**: 在 `workflow_service.py` 中添加数据转换逻辑:

```python
def get_workflow_info(self, run_id: str) -> Dict[str, Any]:
    response = requests.get(f"{self.base_url}/api/workflow/{run_id}")
    raw_data = response.json()

    # 转换为标准格式
    return {
        'runId': raw_data.get('run_id', run_id),
        'status': raw_data.get('status', 'unknown'),
        'nodes': raw_data.get('nodes', {}),
        'steps': raw_data.get('steps', []),
        'costMs': raw_data.get('costMs', 0),
        'output': raw_data.get('output'),
        # 处理interrupted状态
        'lastInterruptedNodeId': raw_data.get('interrupted_node_id'),
        'checkpointExpireTimestamp': raw_data.get('expire_time'),
        'msg': raw_data.get('message'),
        # 处理fail状态
        'error': raw_data.get('error_message')
    }
```

### Q2: 如何处理工作流服务的认证？

**A**: 在 `RealWorkflowService` 中添加认证头:

```python
def __init__(self, base_url: str, api_key: str = None):
    self.base_url = base_url.rstrip('/')
    self.timeout = 300
    self.api_key = api_key

def _get_headers(self):
    headers = {'Content-Type': 'application/json'}
    if self.api_key:
        headers['Authorization'] = f"Bearer {self.api_key}"
    return headers

def start_workflow(self, user_input: str) -> str:
    response = requests.post(
        f"{self.base_url}/api/workflow/start",
        json={"input": user_input},
        headers=self._get_headers(),
        timeout=self.timeout
    )
    # ... 其余代码
```

### Q3: 工作流执行时间过长导致超时怎么办？

**A**:
1. 增加 `workflow_service.py` 中的 `timeout` 值
2. 在 `flask_app.py` 中使用后台任务而不是等待完成
3. 前端已经实现了轮询机制，可以处理长时间运行的任务

### Q4: 如何支持恢复中断的工作流（而不是创建新的）？

**A**: 如果你的实际工作流服务支持恢复，修改 `flask_app.py`:

```python
# 在send_message函数中
if session.waiting_for_input and session.current_run_id:
    # 使用实际工作流的恢复API
    run_id = workflow_service.resume_workflow(
        old_run_id=session.current_run_id,
        user_input=user_message
    )
    session.waiting_for_input = False
else:
    run_id = workflow_service.start_workflow(user_message)
```

并在 `workflow_service.py` 中添加:

```python
def resume_workflow(self, old_run_id: str, user_input: str) -> str:
    """恢复被中断的工作流"""
    url = f"{self.base_url}/api/workflow/{old_run_id}/resume"
    response = requests.post(
        url,
        json={"input": user_input},
        timeout=self.timeout
    )
    response.raise_for_status()
    data = response.json()
    return data["new_run_id"]  # 或返回同一个run_id
```

### Q5: 如何调试工作流调用？

**A**: 启用详细日志:

```python
# 在flask_app.py开头
import logging
logging.basicConfig(level=logging.DEBUG)

# 在workflow_service.py中
logger.setLevel(logging.DEBUG)
```

查看日志输出：
- Flask应用日志显示在控制台
- 工作流服务调用日志包含完整的请求和响应

---

## 快速检查清单

在部署到生产环境前，请确认:

- [ ] 实际工作流服务已实现所需的API端点
- [ ] `workflow_service.py` 中的 `WORKFLOW_SERVICE_URL` 已正确配置
- [ ] 网络连接正常（Flask可以访问工作流服务）
- [ ] 认证配置正确（如果需要）
- [ ] 超时时间设置合理
- [ ] 错误处理逻辑完善
- [ ] 日志级别正确（生产环境建议使用INFO或WARNING）
- [ ] 已进行端到端测试
- [ ] 前端UI显示正确
- [ ] 会话管理正常工作

---

## 联系与支持

如有问题，请查看:
1. 代码注释（每个文件都有详细的文档）
2. 日志输出（启用DEBUG级别）
3. Flask调试界面（开发模式下）

祝集成顺利！🎉

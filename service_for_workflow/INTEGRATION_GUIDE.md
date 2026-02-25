# Workflow 对话应用集成与二次开发指南

> 适用场景：基于大模型的“数据分析 / 数据比较 / 离群点识别 / 控制变量分析”对话应用。

本文档围绕你提供的三个真实函数接口，给出**可直接落地**的集成方案：

1. `runworkflow(user_input: str) -> str`
2. `getflowinfo(run_id: str) -> dict`
3. `resumeflow(user_input: str, run_id: str) -> None`

---

## 1. 当前仓库重构后的核心架构

```
前端(index.html)
    ↓
Flask API (flask_app.py)
    ↓
workflow_adapter.py  (统一输入校验 + 错误转换)
    ↓
workflow_backend.py  (后端选择器)
    ├── MockWorkflowBackend（本地模拟）
    └── ExternalWorkflowFunctionsBackend（接入你的真实3函数）
    ↓
异步轮询(async_processor.py) + 会话管理(session_manager.py)
```

### 这次整理的重点

- 把“流程编排能力”从 Flask 业务路由中拆出来，统一到 `workflow_adapter.py` + `workflow_backend.py`。
- 支持通过环境变量切换 `mock` / `external` 后端，不需要改业务代码。
- 在适配层增加参数校验，避免错误输入导致隐蔽异常。
- 更新配置中心 `config.py`，统一 Flask 和异步轮询参数。

---

## 2. 三个真实函数的接入方案（推荐）

你目前无法提供完整代码，这没关系。推荐使用“**外部函数桥接**”方式，最小改造、最稳定。

### 2.1 创建外部函数文件

在 `service_for_workflow/` 下创建 `external_workflow.py`，实现你的真实调用逻辑：

```python
# service_for_workflow/external_workflow.py
from typing import Dict, Any


def runworkflow(user_input: str) -> str:
    # TODO: 调你们真实服务（HTTP/RPC/SDK）
    # return run_id
    raise NotImplementedError


def getflowinfo(run_id: str) -> Dict[str, Any]:
    # TODO: 调你们真实服务，返回统一结构字典
    raise NotImplementedError


def resumeflow(user_input: str, run_id: str) -> None:
    # TODO: 调你们真实服务恢复执行
    raise NotImplementedError
```

### 2.2 配置环境变量切换到 external

```bash
export WORKFLOW_BACKEND=external
export WORKFLOW_EXTERNAL_MODULE=external_workflow
export WORKFLOW_EXTERNAL_RUN_FUNC=runworkflow
export WORKFLOW_EXTERNAL_INFO_FUNC=getflowinfo
export WORKFLOW_EXTERNAL_RESUME_FUNC=resumeflow
```

> 默认是 `WORKFLOW_BACKEND=mock`，用于本地开发联调。

### 2.3 运行应用

```bash
cd service_for_workflow
python flask_app.py
```

此时 Flask 层会自动使用你的三函数，不需要再改路由代码。

---

## 3. getflowinfo 返回结构规范（必须对齐）

前端和轮询逻辑依赖如下字段，请确保你的真实返回包含它们：

```python
{
  "runId": "...",
  "status": "processing|interrupted|success|fail",
  "nodes": {
    "node_id": {
      "input": {...},
      "output": {...},
      "status": "pending|processing|success|interrupted|fail",
      "costMs": 123,
      "nodeType": "start|flow|condition|end"
    }
  },
  "steps": ["node_id_1", "node_id_2"],
  "costMs": 1000,
  "output": {...},

  # interrupted 时建议返回
  "lastInterruptedNodeId": "...",
  "checkpointExpireTimestamp": 1736000000000,
  "msg": "请补充分析维度",

  # fail 时建议返回
  "error": "错误原因"
}
```

### 状态语义约束

- `processing`：继续轮询。
- `interrupted`：系统等待用户补充输入，然后调用 `resumeflow(user_input, run_id)`。
- `success`：结束流程，`output` 用于回复用户。
- `fail`：结束流程，`error` 反馈给用户。

---

## 4. 与“数据分析/比较/离群点/控制变量”目标对齐建议

建议你在真实工作流中固定四段节点模板：

1. **数据准备节点**：范围、维度、过滤条件标准化。
2. **对比分析节点**：同比/环比/分组比较。
3. **离群点识别节点**：IQR/Z-score/Isolation Forest 三选一（可参数化）。
4. **控制变量分析节点**：固定变量集（如地区、时间、渠道）后做差异归因。

并通过 `output` 返回结构化结果，例如：

```python
{
  "summary": "本期销量下降主要来自华东渠道，异常集中在A品类。",
  "details": {
    "comparison": {...},
    "outliers": [...],
    "controlled_analysis": {...},
    "recommendation": [...]
  }
}
```

这样前端无需改动就能显示结论和细节。

---

## 5. 错误处理与稳定性建议（生产必做）

1. `runworkflow` 超时要可重试（幂等键建议：session_id + message_id）。
2. `getflowinfo` 建议返回“可重入”的状态；轮询失败不应改变工作流状态。
3. `resumeflow` 要检查 run_id 是否处于可恢复状态，避免误恢复。
4. 所有异常统一映射为业务错误码，前端只显示可理解提示。
5. 记录链路日志：`session_id`, `run_id`, `status`, `costMs`, `error`。

---

## 6. 二次开发落地清单

- [ ] 新建 `external_workflow.py` 并接入真实三函数。
- [ ] 对齐 `getflowinfo` 字段规范。
- [ ] 设置 `WORKFLOW_BACKEND=external` 并联调。
- [ ] 执行验证脚本：`python validate_integration.py`。
- [ ] 压测轮询接口并优化 `WORKFLOW_POLL_INTERVAL_SECONDS`。
- [ ] 补充真实业务样例（成功/中断/失败三类）。

---

## 7. 快速排错

### Q1: 为什么发送消息后一直 processing？

- 检查真实 `getflowinfo` 是否永远返回 processing。
- 检查 run_id 是否正确传递且一致。

### Q2: 中断后发送补充信息没生效？

- 检查 `resumeflow` 是否使用同一个 run_id（不能新建 run_id）。
- 检查中断恢复后状态是否回到 processing 并可继续到 success/fail。

### Q3: 前端节点进度显示异常？

- 检查 `steps` 顺序是否与 `nodes` 键一致。
- 检查节点 `status` 是否使用规范枚举值。

---

## 8. 最小可运行 external 示例（占位）

```python
# 仅示意：把真实调用替换进去
from typing import Dict, Any
import requests

BASE_URL = "http://your-workflow-service"


def runworkflow(user_input: str) -> str:
    resp = requests.post(f"{BASE_URL}/run", json={"input": user_input}, timeout=30)
    resp.raise_for_status()
    return resp.json()["run_id"]


def getflowinfo(run_id: str) -> Dict[str, Any]:
    resp = requests.get(f"{BASE_URL}/run/{run_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def resumeflow(user_input: str, run_id: str) -> None:
    resp = requests.post(f"{BASE_URL}/run/{run_id}/resume", json={"input": user_input}, timeout=30)
    resp.raise_for_status()
```

> 你可以直接复制此模板，先打通链路，再逐步补充业务字段。


## 9. 针对真实外部服务常见问题的代码策略（已落地）

### 9.1 仅返回“已执行节点”时如何展示进度

当 `getflowinfo` 的 `nodes` 只包含已执行节点、未返回完整 DAG 时，系统不再依赖“固定节点总数”计算进度，改为：

- 保存 run 的上一次快照；
- 每次轮询计算 `new_nodes_count` 与 `status_changes`；
- 在前端展示“基于连续状态对比”的变更时间线。

这样即使没有完整节点列表，也能让用户看到流程正在推进。

### 9.2 resumeflow 后首轮仍返回旧 interrupted 的处理

部分工作流服务在恢复后会短暂返回一次“旧中断信息”。系统增加了 `resume_pending` 保护逻辑：

- 恢复调用后先将会话切换为恢复态；
- 若轮询拿到与上次相同的中断消息，前端继续显示“恢复中”，不要求用户再次输入；
- 一旦状态进入 processing/success/fail，自动解除恢复保护。

该机制可避免“用户要输入两次，后端却只接收第一次”的体验问题。

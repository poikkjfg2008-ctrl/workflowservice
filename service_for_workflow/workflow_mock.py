"""
工作流服务模拟 - 按照实际工作流服务结构设计
支持节点级别的状态跟踪和动态状态转换
"""
import time
import random
from typing import Dict, Any, List
from enum import Enum


class WorkflowStatus(Enum):
    """工作流状态"""
    PROCESSING = "processing"      # 处理中
    INTERRUPTED = "interrupted"    # 中断（需要更多信息）
    SUCCESS = "success"           # 成功
    FAIL = "fail"                 # 失败


class NodeType(Enum):
    """节点类型"""
    START = "start"        # 开始节点
    FLOW = "flow"          # 流程节点
    CONDITION = "condition"  # 条件节点
    END = "end"           # 结束节点


class WorkflowService:
    """工作流服务（模拟）- 按照实际工作流服务API结构"""

    def __init__(self):
        self._counter = 0
        # 维护每个 run_id 的状态信息
        self._workflow_states: Dict[str, Dict[str, Any]] = {}

    def start_workflow(self, user_input: str) -> str:
        """
        启动工作流

        Args:
            user_input: 用户输入语句

        Returns:
            run_id: 工作流运行实例ID
        """
        self._counter += 1
        run_id = f"{self._counter:025d}"  # 生成25位数字ID，模拟真实格式
        print(f"[Workflow] 启动: {run_id}, 输入: {user_input}")

        # 生成工作流节点（模拟实际工作流结构）
        nodes = self._generate_workflow_nodes()

        # 初始化工作流状态
        self._workflow_states[run_id] = {
            'query_count': 0,
            'status': WorkflowStatus.PROCESSING,
            'nodes': nodes,
            'steps': list(nodes.keys()),  # 节点执行顺序
            'cost_ms': 0,
            'output': None,
            'final_state': None,  # 用于确定最终状态
            'interrupted_node': None,  # 中断节点
            'interrupt_msg': None,  # 中断消息
            'fail_reason': None,  # 失败原因
        }

        return run_id

    def get_workflow_info(self, run_id: str) -> Dict[str, Any]:
        """
        获取工作流信息 - 按照实际API格式返回

        状态转换规则：
        - 第 1-3 次查询返回 processing（模拟节点逐步完成）
        - 第 4 次查询根据 run_id 决定最终状态 (interrupted/success/fail)

        Returns:
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
            }
        """
        if run_id not in self._workflow_states:
            raise ValueError(f"Run ID {run_id} 不存在")

        state = self._workflow_states[run_id]
        state['query_count'] += 1
        query_count = state['query_count']

        # 更新总耗时
        state['cost_ms'] += random.randint(500, 2000)

        # 第 1-3 次查询：逐步完成节点
        if query_count <= 3:
            return self._get_processing_state(run_id, state, query_count)

        # 第 4 次查询：确定最终状态
        return self._get_final_state(run_id, state)

    def resume_workflow(self, user_input: str, run_id: str) -> None:
        """恢复中断工作流，保持原 run_id。"""
        if run_id not in self._workflow_states:
            raise ValueError(f"Run ID {run_id} 不存在")

        state = self._workflow_states[run_id]
        state['status'] = WorkflowStatus.PROCESSING
        state['query_count'] = 0
        state['interrupt_msg'] = f"用户补充信息: {user_input}"

    def _get_processing_state(self, run_id: str, state: Dict[str, Any], query_count: int) -> Dict[str, Any]:
        """生成 processing 状态的响应"""
        nodes = state['nodes']
        steps = state['steps']

        # 将前 query_count 个节点标记为 success，当前节点为 processing
        for i, node_id in enumerate(steps):
            if i < query_count - 1:
                nodes[node_id]['status'] = 'success'
                nodes[node_id]['costMs'] = random.randint(100, 1000)
            elif i == query_count - 1:
                nodes[node_id]['status'] = 'processing'
                nodes[node_id]['costMs'] = random.randint(100, 500)
            else:
                nodes[node_id]['status'] = 'pending'
                nodes[node_id]['costMs'] = 0

        return {
            'runId': run_id,
            'status': 'processing',
            'nodes': nodes,
            'steps': steps,
            'costMs': state['cost_ms'],
            'output': None
        }

    def _get_final_state(self, run_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成最终状态（interrupted/success/fail）的响应"""
        nodes = state['nodes']
        steps = state['steps']

        # 使用 run_id 的最后一位数字决定状态
        final_type = int(run_id[-1]) % 3

        # 标记所有节点状态
        for node_id in steps:
            nodes[node_id]['status'] = 'success'
            nodes[node_id]['costMs'] = random.randint(100, 1000)

        if final_type == 0:
            # INTERRUPTED 状态
            interrupted_node_id = steps[len(steps) // 2]  # 选择中间节点作为中断点
            nodes[interrupted_node_id]['status'] = 'interrupted'

            state['status'] = WorkflowStatus.INTERRUPTED
            state['interrupted_node'] = interrupted_node_id
            state['interrupt_msg'] = "需要更多信息：请提供数据范围（如：近7天/近30天）和分析维度（如：按产品/按地区）"

            return {
                'runId': run_id,
                'status': 'interrupted',
                'nodes': nodes,
                'steps': steps,
                'costMs': state['cost_ms'],
                'output': None,
                'lastInterruptedNodeId': interrupted_node_id,
                'checkpointExpireTimestamp': int(time.time() * 1000) + 3600000,  # 1小时后过期
                'msg': state['interrupt_msg']
            }

        elif final_type == 1:
            # SUCCESS 状态
            state['status'] = WorkflowStatus.SUCCESS
            state['output'] = {
                'summary': '分析完成！数据显示过去一个月销售额增长了25%',
                'details': {
                    'total_sales': '1,250,000',
                    'growth_rate': '+25%',
                    'top_products': ['产品A', '产品B', '产品C'],
                    'recommendation': '建议继续加大产品A和B的推广力度'
                }
            }

            return {
                'runId': run_id,
                'status': 'success',
                'nodes': nodes,
                'steps': steps,
                'costMs': state['cost_ms'],
                'output': state['output']
            }

        else:
            # FAIL 状态
            fail_node_id = steps[len(steps) // 3]  # 选择前1/3节点作为失败点
            nodes[fail_node_id]['status'] = 'fail'

            state['status'] = WorkflowStatus.FAIL
            state['fail_reason'] = '数据处理失败：连接数据库超时，请检查网络连接后重试'

            return {
                'runId': run_id,
                'status': 'fail',
                'nodes': nodes,
                'steps': steps,
                'costMs': state['cost_ms'],
                'output': None,
                'error': state['fail_reason']
            }

    def _generate_workflow_nodes(self) -> Dict[str, Dict[str, Any]]:
        """生成模拟的工作流节点结构"""
        # 生成5个节点：start -> flow -> condition -> flow -> end
        node_templates = [
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.START,
                'input': {'user_query': '...', 'start_time': '...'},
                'output': {'session_id': '...', 'status': 'initialized'}
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.FLOW,
                'input': {'data_source': 'database', 'query': 'SELECT * FROM ...'},
                'output': {'rows': 1000, 'columns': ['id', 'name', 'value']}
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.CONDITION,
                'input': {
                    'branches': [
                        {'conditions': [{'Left': True, 'Right': True, 'func': 'equal'}], 'operation': 'and'},
                        {'conditions': [{'Left': False, 'Right': True, 'func': 'greater'}], 'operation': 'or'}
                    ],
                    'operation': 'and'
                },
                'output': True
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.FLOW,
                'input': {'algorithm': 'linear_regression', 'features': ['price', 'quantity']},
                'output': {'accuracy': 0.95, 'predictions': [1, 2, 3, 4, 5]}
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.END,
                'input': {'result_format': 'json', 'include_charts': True},
                'output': {'status': 'completed', 'chart_url': 'https://example.com/chart/123'}
            }
        ]

        nodes = {}
        for template in node_templates:
            node_id = template['id']
            nodes[node_id] = {
                'input': template['input'],
                'output': template['output'],
                'status': 'pending',  # pending/processing/success/interrupted/fail
                'costMs': 0,
                'nodeType': template['type'].value
            }

        return nodes


# 全局实例
workflow_service = WorkflowService()

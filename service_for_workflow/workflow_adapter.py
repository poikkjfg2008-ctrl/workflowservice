"""
工作流适配器 - 实现三个核心函数接口

这是实际工作流服务的适配器层，提供三个函数：
1. runworkflow(user_input: str) -> str
2. getflowinfo(run_id: str) -> dict
3. resumeflow(user_input: str, run_id: str) -> None

您可以将此文件中的模拟实现替换为实际的工作流服务调用
"""
import time
import random
from typing import Dict, Any, List, Optional
from enum import Enum


class WorkflowStatus(Enum):
    """工作流状态"""
    PROCESSING = "processing"
    INTERRUPTED = "interrupted"
    SUCCESS = "success"
    FAIL = "fail"


class NodeType(Enum):
    """节点类型"""
    START = "start"
    FLOW = "flow"
    CONDITION = "condition"
    END = "end"


class WorkflowAdapter:
    """
    工作流适配器 - 实现三个核心函数

    您可以继承此类并重写方法，或将内部实现替换为实际的服务调用
    """

    def __init__(self):
        self._counter = 0
        # 维护每个 run_id 的状态信息
        self._workflow_states: Dict[str, Dict[str, Any]] = {}
        # 维护中断后恢复的状态
        self._resumed_states: Dict[str, str] = {}  # run_id -> 新的输入信息

    def runworkflow(self, user_input: str) -> str:
        """
        启动工作流

        Args:
            user_input: 用户输入语句

        Returns:
            run_id: 工作流运行实例ID
        """
        self._counter += 1
        run_id = f"{self._counter:025d}"  # 生成25位数字ID
        print(f"[WorkflowAdapter] 启动工作流: {run_id}, 输入: {user_input}")

        # 生成工作流节点
        nodes = self._generate_workflow_nodes()

        # 初始化工作流状态
        self._workflow_states[run_id] = {
            'query_count': 0,
            'status': WorkflowStatus.PROCESSING,
            'nodes': nodes,
            'steps': list(nodes.keys()),
            'costMs': 0,
            'output': None,
            'lastInterruptedNodeId': None,
            'checkpointExpireTimestamp': None,
            'msg': None,
            'error': None,
            'is_resumed': False  # 标记是否是恢复后的工作流
        }

        return run_id

    def getflowinfo(self, run_id: str) -> Dict[str, Any]:
        """
        查询工作流信息

        Args:
            run_id: 工作流运行ID

        Returns:
            工作流信息字典，包含：
            - runId: str
            - status: str (processing/interrupted/success/fail)
            - nodes: Dict[str, NodeInfo]
            - steps: List[str]
            - costMs: int
            - output: Any (成功时有值)
            - lastInterruptedNodeId: str (中断状态时有值)
            - checkpointExpireTimestamp: int (中断状态时有值)
            - msg: str (中断状态时的消息)
            - error: str (失败状态时的错误)

        Raises:
            ValueError: 当 run_id 不存在时
        """
        if run_id not in self._workflow_states:
            raise ValueError(f"Run ID {run_id} 不存在")

        state = self._workflow_states[run_id]
        state['query_count'] += 1
        query_count = state['query_count']

        # 更新总耗时
        state['costMs'] += random.randint(500, 2000)

        # 如果是恢复后的工作流，使用不同的逻辑
        if state['is_resumed']:
            return self._get_resumed_workflow_state(run_id, state, query_count)

        # 第 1-3 次查询：逐步完成节点
        if query_count <= 3:
            return self._get_processing_state(run_id, state, query_count)

        # 第 4 次查询：确定最终状态
        return self._get_final_state(run_id, state)

    def resumeflow(self, user_input: str, run_id: str) -> None:
        """
        恢复中断的工作流

        Args:
            user_input: 用户针对中断信息的补充输入
            run_id: 被中断的工作流运行ID（保持不变）

        Note:
            此函数不返回值，恢复后的工作流继续使用原 run_id
        """
        if run_id not in self._workflow_states:
            raise ValueError(f"Run ID {run_id} 不存在")

        state = self._workflow_states[run_id]

        if state['status'] != WorkflowStatus.INTERRUPTED:
            print(f"[WorkflowAdapter] 警告: 工作流 {run_id} 不是中断状态，当前状态: {state['status'].value}")

        print(f"[WorkflowAdapter] 恢复工作流: {run_id}, 输入: {user_input}")

        # 标记为恢复状态
        state['is_resumed'] = True
        state['query_count'] = 0  # 重置查询计数
        state['status'] = WorkflowStatus.PROCESSING
        state['lastInterruptedNodeId'] = None
        state['checkpointExpireTimestamp'] = None
        state['msg'] = None

        # 保存用户输入（模拟）
        self._resumed_states[run_id] = user_input

    def _get_processing_state(self, run_id: str, state: Dict[str, Any], query_count: int) -> Dict[str, Any]:
        """生成 processing 状态的响应"""
        nodes = state['nodes']
        steps = state['steps']

        # 将前 query_count-1 个节点标记为 success，当前节点为 processing
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
            'costMs': state['costMs'],
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
            interrupted_node_id = steps[len(steps) // 2]
            nodes[interrupted_node_id]['status'] = 'interrupted'

            state['status'] = WorkflowStatus.INTERRUPTED
            state['lastInterruptedNodeId'] = interrupted_node_id
            state['checkpointExpireTimestamp'] = int(time.time() * 1000) + 3600000
            state['msg'] = "需要更多信息：请提供数据范围（如：近7天/近30天）和分析维度（如：按产品/按地区）"

            return {
                'runId': run_id,
                'status': 'interrupted',
                'nodes': nodes,
                'steps': steps,
                'costMs': state['costMs'],
                'output': None,
                'lastInterruptedNodeId': interrupted_node_id,
                'checkpointExpireTimestamp': state['checkpointExpireTimestamp'],
                'msg': state['msg']
            }

        elif final_type == 1:
            # SUCCESS 状态
            state['status'] = WorkflowStatus.SUCCESS
            state['output'] = {
                'summary': '分析完成！数据显示过去一个月销售额增长了25%。\n\n详细结果：\n- 总销售额: 1,250,000 元\n- 增长率: +25%\n- 热门产品: 产品A、产品B、产品C\n- 建议: 继续加大产品A和B的推广力度，重点关注华东市场',
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
                'costMs': state['costMs'],
                'output': state['output']
            }

        else:
            # FAIL 状态
            fail_node_id = steps[len(steps) // 3]
            nodes[fail_node_id]['status'] = 'fail'

            state['status'] = WorkflowStatus.FAIL
            state['error'] = '数据处理失败：连接数据库超时，请检查网络连接后重试'

            return {
                'runId': run_id,
                'status': 'fail',
                'nodes': nodes,
                'steps': steps,
                'costMs': state['costMs'],
                'output': None,
                'error': state['error']
            }

    def _get_resumed_workflow_state(self, run_id: str, state: Dict[str, Any], query_count: int) -> Dict[str, Any]:
        """
        生成恢复后工作流的状态

        恢复后的工作流：
        - 第1-2次查询返回 processing
        - 第3次查询返回 success
        """
        nodes = state['nodes']
        steps = state['steps']

        if query_count <= 2:
            # Processing 状态
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
                'costMs': state['costMs'],
                'output': None
            }
        else:
            # Success 状态
            for node_id in steps:
                nodes[node_id]['status'] = 'success'
                nodes[node_id]['costMs'] = random.randint(100, 1000)

            state['status'] = WorkflowStatus.SUCCESS
            user_input = self._resumed_states.get(run_id, '')

            state['output'] = {
                'summary': f'感谢您的补充信息："{user_input}"。\n\n工作流已成功完成！\n\n分析结果：\n- 数据范围已更新\n- 分析维度已应用\n- 生成报告已完成',
                'details': {
                    'user_input': user_input,
                    'completion_time': time.strftime('%Y-%m-%d %H:%M:%S')
                }
            }

            return {
                'runId': run_id,
                'status': 'success',
                'nodes': nodes,
                'steps': steps,
                'costMs': state['costMs'],
                'output': state['output']
            }

    def _generate_workflow_nodes(self) -> Dict[str, Dict[str, Any]]:
        """生成模拟的工作流节点结构"""
        # 生成5个节点：start -> flow -> condition -> flow -> end
        node_templates = [
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.START,
                'input': {'para1': 'user_query', 'para2': 'start_time'},
                'output': {'para1': 'session_id', 'para2': 'initialized'}
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.FLOW,
                'input': {'para1': 'database', 'para2': 'SELECT * FROM ...'},
                'output': {'para1': '1000', 'para2': 'id,name,value'}
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.CONDITION,
                'input': {
                    'branches': [
                        {
                            'conditions': [
                                {'Left': True, 'Right': True, 'func': 'equal'}
                            ],
                            'operation': 'and'
                        }
                    ],
                    'operation': 'and'
                },
                'output': 'true'
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.FLOW,
                'input': {'para1': 'linear_regression', 'para2': 'price,quantity'},
                'output': {'para1': '0.95', 'para2': '1,2,3,4,5'}
            },
            {
                'id': 'd' + ''.join([str(random.randint(0, 9)) for _ in range(23)]),
                'type': NodeType.END,
                'input': {'para1': 'json', 'para2': 'true'},
                'output': {'para1': 'completed', 'para2': 'report_id_12345'}
            }
        ]

        nodes = {}
        for template in node_templates:
            node_id = template['id']
            nodes[node_id] = {
                'input': template['input'],
                'output': template['output'],
                'status': 'pending',
                'costMs': 0,
                'nodeType': template['type'].value
            }

        return nodes


# ============================================
# 全局实例和三个核心函数
# ============================================

_workflow_adapter = WorkflowAdapter()


def runworkflow(user_input: str) -> str:
    """
    启动工作流

    Args:
        user_input: 用户输入语句

    Returns:
        run_id: 工作流运行实例ID
    """
    return _workflow_adapter.runworkflow(user_input)


def getflowinfo(run_id: str) -> Dict[str, Any]:
    """
    查询工作流信息

    Args:
        run_id: 工作流运行ID

    Returns:
        工作流信息字典

    Raises:
        ValueError: 当 run_id 不存在时
    """
    return _workflow_adapter.getflowinfo(run_id)


def resumeflow(user_input: str, run_id: str) -> None:
    """
    恢复中断的工作流

    Args:
        user_input: 用户针对中断信息的补充输入
        run_id: 被中断的工作流运行ID（保持不变）

    Note:
        此函数不返回值，恢复后的工作流继续使用原 run_id
    """
    _workflow_adapter.resumeflow(user_input, run_id)

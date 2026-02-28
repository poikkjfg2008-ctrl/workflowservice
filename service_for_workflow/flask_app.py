"""Flask Web应用 - 智能对话工作流系统"""
from __future__ import annotations

from copy import deepcopy
from flask import Flask, render_template, request, jsonify, session as flask_session
from typing import Dict, Any, List

from config import Config
from workflow_adapter import runworkflow, getflowinfo, resumeflow
from session_manager import session_manager
from async_processor import async_processor


app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
_CLIENT_SESSION_KEY = 'workflow_session_id'


# run_id -> 上一次状态快照（用于增量进度展示）
_RUN_SNAPSHOT_CACHE: Dict[str, Dict[str, Any]] = {}


def _session_for_run(run_id: str):
    """根据 run_id 找到对应会话。"""
    for s in session_manager.get_all_sessions():
        if s.current_run_id == run_id:
            return s
    return None


def _get_or_create_client_session(force_new: bool = False):
    """按设备（浏览器 cookie）获取或创建会话。"""
    if force_new:
        session = session_manager.create_session()
        flask_session[_CLIENT_SESSION_KEY] = session.session_id
        return session

    session_id = flask_session.get(_CLIENT_SESSION_KEY)
    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            return session

    session = session_manager.create_session()
    flask_session[_CLIENT_SESSION_KEY] = session.session_id
    return session


def _status_rank(status: str) -> int:
    order = {
        'pending': 0,
        'processing': 1,
        'interrupted': 1,
        'success': 2,
        'fail': 2,
    }
    return order.get(status, 0)


def _snapshot_from_workflow_info(workflow_info: Dict[str, Any]) -> Dict[str, Any]:
    """提取当前工作流快照。"""
    nodes = workflow_info.get('nodes') or {}
    steps = workflow_info.get('steps') or list(nodes.keys())

    # 兼容部分图返回：步骤里可能没有全部节点
    ordered_nodes: List[str] = []
    for node_id in steps:
        if node_id in nodes:
            ordered_nodes.append(node_id)
    for node_id in nodes.keys():
        if node_id not in ordered_nodes:
            ordered_nodes.append(node_id)

    node_statuses = {
        node_id: (nodes.get(node_id, {}) or {}).get('status', 'pending')
        for node_id in ordered_nodes
    }

    return {
        'workflow_status': workflow_info.get('status', ''),
        'ordered_nodes': ordered_nodes,
        'node_statuses': node_statuses,
    }


def _build_progress_info(run_id: str, workflow_info: Dict[str, Any]) -> Dict[str, Any]:
    """基于前后快照构建增量进度信息。"""
    current = _snapshot_from_workflow_info(workflow_info)
    previous = deepcopy(_RUN_SNAPSHOT_CACHE.get(run_id))
    _RUN_SNAPSHOT_CACHE[run_id] = deepcopy(current)

    ordered_nodes = current['ordered_nodes']
    node_statuses = current['node_statuses']

    total_steps = len(ordered_nodes)
    done_count = sum(1 for s in node_statuses.values() if s in {'success', 'fail'})
    running_count = sum(1 for s in node_statuses.values() if s in {'processing', 'interrupted'})

    if total_steps > 0:
        percentage = int(((done_count + 0.5 * running_count) / total_steps) * 100)
        percentage = max(1, min(99, percentage))
    else:
        percentage = 1

    current_node = ''
    for node_id in ordered_nodes:
        if node_statuses.get(node_id) in {'processing', 'interrupted'}:
            current_node = node_id
            break
    if not current_node and ordered_nodes:
        current_node = ordered_nodes[min(done_count, total_steps - 1)]

    status_changes = []
    new_nodes_count = len(ordered_nodes)

    if previous:
        prev_nodes = set(previous.get('ordered_nodes', []))
        new_nodes_count = len([node_id for node_id in ordered_nodes if node_id not in prev_nodes])
        prev_statuses = previous.get('node_statuses', {})

        for node_id in ordered_nodes:
            cur = node_statuses.get(node_id, 'pending')
            prev = prev_statuses.get(node_id)
            if prev is None:
                continue
            if prev != cur and _status_rank(cur) >= _status_rank(prev):
                node = (workflow_info.get('nodes') or {}).get(node_id, {})
                status_changes.append({
                    'nodeId': node_id,
                    'nodeType': node.get('nodeType', 'unknown'),
                    'from': prev,
                    'to': cur,
                })

    progress = {
        'current_step': done_count,
        'total_steps': total_steps,
        'percentage': percentage,
        'current_node': current_node,
        'nodes': ordered_nodes,
        'new_nodes_count': new_nodes_count,
        'status_changes_count': len(status_changes),
        'status_changes': status_changes,
        'is_partial_graph': not bool(workflow_info.get('steps')),
    }

    # processing 场景最高 99%，最终态由后端状态驱动
    progress['percentage'] = min(progress['percentage'], 99)
    return progress


# ============================================
# 异步工作流回调
# ============================================

async def workflow_callback(session_id: str, result: Dict[str, Any]):
    """工作流状态回调"""
    session = session_manager.get_session(session_id)
    if not session:
        return

    status = result.get("status", "")

    if status == "interrupted":
        msg = result.get("msg", "工作流被中断，需要更多信息")

        # 恢复后短暂同步窗口：忽略“旧中断回放”
        if session.resume_pending and session.last_interrupt_msg == msg:
            return

        session.resume_pending = False
        session.waiting_for_input = True
        session.last_interrupt_msg = msg
        session.add_message("assistant", msg)

    elif status == "success":
        session.waiting_for_input = False
        session.resume_pending = False
        output = result.get("output", {})
        message = format_success_output(output)

        session.add_message("assistant", message)

    elif status == "fail":
        session.waiting_for_input = False
        session.resume_pending = False
        error_msg = result.get("error", "工作流执行失败")
        session.add_message("assistant", f"❌ {error_msg}")


def format_dict_to_text(d: Dict[str, Any], indent: int = 0) -> str:
    """将字典格式化为文本"""
    lines = []
    prefix = "  " * indent
    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(format_dict_to_text(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    return "\n".join(lines)


def format_success_output(output: Any) -> str:
    """将 success output 统一格式化为可展示文本。"""
    if isinstance(output, dict):
        # 兼容外部系统常见字段命名：summary / message / msg / mes
        message = (
            output.get("summary")
            or output.get("message")
            or output.get("msg")
            or output.get("mes")
            or "工作流执行完成"
        )

        details = (
            output.get("details")
            or output.get("data")
            or output.get("result")
        )
        if details and isinstance(details, dict):
            message += f"\n\n详细信息：\n{format_dict_to_text(details)}"
        elif details:
            message += f"\n\n详细信息：\n{details}"
        return message
    if output is None:
        return "工作流执行完成"
    return str(output)


# ============================================
# 路由处理
# ============================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/session', methods=['GET', 'POST'])
def handle_session():
    if request.method == 'POST':
        session = _get_or_create_client_session(force_new=True)
        return jsonify({'success': True, 'session_id': session.session_id, 'message': '会话已创建'})

    session = _get_or_create_client_session()
    return jsonify({
        'success': True,
        'session_id': session.session_id,
        'message_count': len(session.messages),
        'waiting_for_input': session.waiting_for_input,
        'current_run_id': session.current_run_id
    })


@app.route('/api/messages', methods=['GET'])
def get_messages():
    session = _get_or_create_client_session()
    messages = [
        {'role': msg.role, 'content': msg.content, 'timestamp': msg.timestamp.isoformat()}
        for msg in session.messages
    ]

    return jsonify({'success': True, 'messages': messages, 'session_id': session.session_id})


@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({'success': False, 'error': '消息不能为空'}), 400

    session = _get_or_create_client_session()

    if session.waiting_for_input and session.current_run_id:
        session.add_message("user", user_message)
        run_id = session.current_run_id

        # 在恢复之前先切换本地状态，避免前端读到陈旧 waiting 标志
        session.waiting_for_input = False
        session.resume_pending = True

        resumeflow(user_message, run_id)
        print(f"[Flask] 中断恢复: run_id={run_id}, 输入={user_message}")
    else:
        if session.current_run_id and not session.waiting_for_input:
            try:
                workflow_info = getflowinfo(session.current_run_id)
                if workflow_info.get('status') == 'processing':
                    return jsonify({
                        'success': False,
                        'error': '当前有工作流正在执行，请等待完成后再发送新消息'
                    }), 409
            except Exception:
                pass

        session.add_message("user", user_message)
        run_id = runworkflow(user_message)
        session.current_run_id = run_id
        session.resume_pending = False
        session.last_interrupt_msg = None
        _RUN_SNAPSHOT_CACHE.pop(run_id, None)
        print(f"[Flask] 启动新工作流: run_id={run_id}, 输入={user_message}")

    async_processor.submit_task(
        session_id=session.session_id,
        run_id=run_id,
        status_callback=workflow_callback
    )

    return jsonify({'success': True, 'run_id': run_id, 'message': '消息已发送，工作流正在处理'})


@app.route('/api/refresh', methods=['POST'])
def refresh_status():
    session = _get_or_create_client_session()
    workflow_status = 'not_started'
    # 兜底：若工作流已success但回调消息未及时写入，会在刷新接口中补齐一次。
    if session.current_run_id:
        try:
            workflow_info = getflowinfo(session.current_run_id)
            workflow_status = workflow_info.get('status', 'not_started')
            if workflow_info.get('status') == 'success':
                success_text = format_success_output(workflow_info.get('output', {}))
                has_success_msg = any(
                    msg.role == 'assistant' and msg.content == success_text
                    for msg in session.messages
                )
                if success_text and not has_success_msg:
                    session.add_message('assistant', success_text)
        except Exception:
            pass

    messages = [
        {'role': msg.role, 'content': msg.content, 'timestamp': msg.timestamp.isoformat()}
        for msg in session.messages
    ]

    return jsonify({
        'success': True,
        'messages': messages,
        'session_id': session.session_id,
        'waiting_for_input': session.waiting_for_input,
        'current_run_id': session.current_run_id,
        'workflow_status': workflow_status,
    })


@app.route('/api/workflow/<run_id>/status', methods=['GET'])
def get_workflow_status(run_id: str):
    try:
        workflow_info = getflowinfo(run_id)
        response = {'success': True, **workflow_info}

        status = workflow_info.get('status', '')
        if status == 'processing':
            response['progress_info'] = _build_progress_info(run_id, workflow_info)
            # 恢复流程进入processing后，解除同步保护
            session = _session_for_run(run_id)
            if session:
                session.resume_pending = False

        elif status == 'interrupted':
            msg = workflow_info.get('msg', '工作流被中断，需要更多信息')
            session = _session_for_run(run_id)

            # 恢复后若短暂拿到旧中断信息，则继续展示为processing，避免用户二次输入
            if session and session.resume_pending and session.last_interrupt_msg == msg:
                response['status'] = 'processing'
                response['message'] = '工作流正在恢复中，请稍候...'
                response['progress_info'] = {
                    'current_step': 0,
                    'total_steps': 0,
                    'percentage': 1,
                    'current_node': 'resuming',
                    'nodes': [],
                    'new_nodes_count': 0,
                    'status_changes_count': 0,
                    'status_changes': [],
                    'is_partial_graph': True,
                }
            else:
                response['message'] = msg

        elif status == 'success':
            _RUN_SNAPSHOT_CACHE.pop(run_id, None)
            output = workflow_info.get('output', {})
            response['message'] = format_success_output(output)
            response['display_output'] = response['message']

        elif status == 'fail':
            _RUN_SNAPSHOT_CACHE.pop(run_id, None)
            response['message'] = workflow_info.get('error', '工作流执行失败')

        return jsonify(response)

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/clear', methods=['POST'])
def clear_chat():
    session = _get_or_create_client_session(force_new=True)
    return jsonify({'success': True, 'session_id': session.session_id, 'message': '对话已清空'})


@app.route('/api/status', methods=['GET'])
def get_status():
    sessions = session_manager.get_all_sessions()
    return jsonify({
        'success': True,
        'active_sessions': len(sessions),
        'active_tasks': async_processor.get_active_tasks_count()
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': '未找到'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': '服务器内部错误'}), 500


def main():
    print("=" * 70)
    print("🚀 Flask智能对话工作流系统启动中...")
    print("=" * 70)
    print(f"📍 服务地址: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    print(f"📊 活跃会话: {len(session_manager.get_all_sessions())}")
    print(f"⚙️  活跃任务: {async_processor.get_active_tasks_count()}")
    print("=" * 70)

    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )


if __name__ == '__main__':
    main()

"""Flask Web应用 - 智能对话工作流系统"""
from __future__ import annotations

from copy import deepcopy
from flask import Flask, render_template, request, jsonify
from typing import Dict, Any

from config import Config
from workflow_adapter import runworkflow, getflowinfo, resumeflow
from session_manager import session_manager
from async_processor import async_processor


app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY


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
        if isinstance(output, dict):
            message = output.get("summary", "工作流执行完成")
            details = output.get("details", {})
            if details:
                message += f"\n\n详细信息：\n{format_dict_to_text(details)}"
        else:
            message = str(output) if output else "工作流执行完成"

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


# ============================================
# 路由处理
# ============================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/session', methods=['GET', 'POST'])
def handle_session():
    if request.method == 'POST':
        session = session_manager.create_session()
        return jsonify({'success': True, 'session_id': session.session_id, 'message': '会话已创建'})

    sessions = session_manager.get_all_sessions()
    session = sessions[-1] if sessions else session_manager.create_session()
    return jsonify({
        'success': True,
        'session_id': session.session_id,
        'message_count': len(session.messages),
        'waiting_for_input': session.waiting_for_input,
        'current_run_id': session.current_run_id
    })


@app.route('/api/messages', methods=['GET'])
def get_messages():
    sessions = session_manager.get_all_sessions()
    if not sessions:
        return jsonify({'success': True, 'messages': []})

    session = sessions[-1]
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

    sessions = session_manager.get_all_sessions()
    session = sessions[-1] if sessions else session_manager.create_session()

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
    sessions = session_manager.get_all_sessions()
    if not sessions:
        return jsonify({'success': False, 'error': '无活动会话'}), 404

    session = sessions[-1]
    messages = [
        {'role': msg.role, 'content': msg.content, 'timestamp': msg.timestamp.isoformat()}
        for msg in session.messages
    ]

    return jsonify({
        'success': True,
        'messages': messages,
        'session_id': session.session_id,
        'waiting_for_input': session.waiting_for_input,
        'current_run_id': session.current_run_id
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
            response['message'] = output.get('summary', '工作流执行完成') if isinstance(output, dict) else str(output or '工作流执行完成')

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
    _RUN_SNAPSHOT_CACHE.clear()
    session = session_manager.create_session()
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

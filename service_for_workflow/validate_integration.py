#!/usr/bin/env python3
"""
工作流集成验证脚本
验证代码的正确性和准备就绪状态
"""
import sys
import os

# 添加service_for_workflow到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """检查依赖是否安装"""
    print("检查依赖...")
    missing = []

    try:
        import flask
        print("  ✓ Flask")
    except ImportError:
        missing.append("Flask")
        print("  ✗ Flask (未安装)")

    try:
        import redis
        print("  ✓ Redis")
    except ImportError:
        missing.append("Redis")
        print("  ✗ Redis (未安装)")

    if missing:
        print(f"\n⚠️  缺少依赖: {', '.join(missing)}")
        print("请运行: pip3 install -r requirements_flask.txt")
        return False

    print("✓ 所有依赖已安装\n")
    return True


def check_workflow_mock():
    """验证workflow_mock.py的正确性"""
    print("检查 workflow_mock.py...")

    try:
        from workflow_mock import workflow_service

        # 测试启动工作流
        run_id = workflow_service.start_workflow("测试输入")
        print(f"  ✓ start_workflow() 返回: {run_id}")

        # 验证run_id格式
        if len(run_id) == 25 and run_id.isdigit():
            print(f"  ✓ run_id 格式正确 (25位数字)")
        else:
            print(f"  ✗ run_id 格式错误: {run_id}")
            return False

        # 测试查询状态（processing）
        info = workflow_service.get_workflow_info(run_id)
        if info['status'] == 'processing':
            print(f"  ✓ 第1次查询返回: {info['status']}")
        else:
            print(f"  ✗ 第1次查询应该返回processing，实际: {info['status']}")
            return False

        # 继续查询直到最终状态
        for i in range(2, 5):
            info = workflow_service.get_workflow_info(run_id)
            print(f"  ✓ 第{i}次查询返回: {info['status']}")

        # 验证数据结构
        required_keys = ['runId', 'status', 'nodes', 'steps', 'costMs']
        for key in required_keys:
            if key not in info:
                print(f"  ✗ 缺少必需字段: {key}")
                return False

        # 验证nodes结构
        nodes = info['nodes']
        steps = info['steps']
        if len(nodes) == 5 and len(steps) == 5:
            print(f"  ✓ 节点数量正确: {len(nodes)}")
        else:
            print(f"  ✗ 节点数量错误: nodes={len(nodes)}, steps={len(steps)}")
            return False

        # 验证节点结构
        for node_id, node in nodes.items():
            required_node_keys = ['input', 'output', 'status', 'costMs', 'nodeType']
            for key in required_node_keys:
                if key not in node:
                    print(f"  ✗ 节点 {node_id} 缺少字段: {key}")
                    return False

        print("  ✓ 节点结构正确")
        print("✓ workflow_mock.py 验证通过\n")
        return True

    except Exception as e:
        print(f"  ✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_flask_app():
    """验证flask_app.py可以正确导入"""
    print("检查 flask_app.py...")

    try:
        # 导入会检查语法错误
        from flask_app import app, workflow_callback, format_dict_to_text
        print("  ✓ flask_app.py 导入成功")

        # 测试format_dict_to_text函数
        test_dict = {
            'key1': 'value1',
            'key2': {'nested_key': 'nested_value'},
            'key3': ['item1', 'item2']
        }
        result = format_dict_to_text(test_dict)
        if 'key1' in result and 'nested_key' in result:
            print("  ✓ format_dict_to_text() 工作正常")
        else:
            print("  ✗ format_dict_to_text() 输出异常")
            return False

        print("✓ flask_app.py 验证通过\n")
        return True

    except Exception as e:
        print(f"  ✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_session_manager():
    """验证session_manager.py"""
    print("检查 session_manager.py...")

    try:
        from session_manager import session_manager, Session

        # 测试创建会话
        session = session_manager.create_session()
        print(f"  ✓ create_session() 返回 session_id: {session.session_id[:20]}...")

        # 测试添加消息
        session.add_message("user", "测试消息")
        if len(session.messages) == 1:
            print("  ✓ add_message() 工作正常")
        else:
            print("  ✗ add_message() 消息数量错误")
            return False

        print("✓ session_manager.py 验证通过\n")
        return True

    except Exception as e:
        print(f"  ✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_async_processor():
    """验证async_processor.py"""
    print("检查 async_processor.py...")

    try:
        from async_processor import async_processor

        # 测试获取活跃任务数
        count = async_processor.get_active_tasks_count()
        print(f"  ✓ get_active_tasks_count() 返回: {count}")

        print("✓ async_processor.py 验证通过\n")
        return True

    except Exception as e:
        print(f"  ✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_html_template():
    """验证HTML模板存在"""
    print("检查 HTML 模板...")

    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(template_path):
        print(f"  ✓ templates/index.html 存在")

        # 读取并检查关键函数
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()

        required_functions = [
            'pollWorkflowStatus',
            'updateNodeDetails',
            'updateWorkflowProgress',
            'sendMessage'
        ]

        for func in required_functions:
            if f'function {func}(' in content:
                print(f"  ✓ 函数 {func}() 存在")
            else:
                print(f"  ✗ 函数 {func}() 不存在")
                return False

        print("✓ HTML 模板验证通过\n")
        return True

    else:
        print(f"  ✗ templates/index.html 不存在")
        return False


def check_integration_readiness():
    """检查集成准备情况"""
    print("检查集成准备情况...")

    # 检查是否存在实际的工作流服务文件
    if os.path.exists('workflow_service.py'):
        print("  ⚠️  检测到 workflow_service.py（实际工作流服务）")
        print("      请确认已配置 WORKFLOW_SERVICE_URL 环境变量")
    else:
        print("  ℹ️  使用 workflow_mock.py（模拟服务）")
        print("      要集成实际服务，请参考 INTEGRATION_GUIDE.md")

    print()
    return True


def main():
    """主检查函数"""
    print("=" * 70)
    print("工作流集成验证脚本")
    print("=" * 70)
    print()

    checks = [
        check_dependencies,
        check_workflow_mock,
        check_flask_app,
        check_session_manager,
        check_async_processor,
        check_html_template,
        check_integration_readiness
    ]

    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"✗ 检查失败: {e}\n")
            results.append(False)

    print("=" * 70)
    print("验证结果汇总")
    print("=" * 70)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✓ 所有检查通过 ({passed}/{total})")
        print()
        print("下一步:")
        print("  1. 安装依赖: pip3 install -r requirements_flask.txt")
        print("  2. 启动应用: python3 flask_app.py")
        print("  3. 访问: http://localhost:5000")
        print()
        print("如需集成实际工作流服务，请参考 INTEGRATION_GUIDE.md")
        return 0
    else:
        print(f"✗ 部分检查失败 ({passed}/{total})")
        print()
        print("请修复上述问题后再试")
        return 1


if __name__ == '__main__':
    sys.exit(main())

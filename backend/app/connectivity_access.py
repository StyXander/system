"""个人演示入口：按部署配置取消组织登录与按日、按次数配额。"""
import os


def single_user_enabled() -> bool:
    # 与供应商凭据、报告证据条件、执行循环边界分别配置。
    return os.getenv('AUDITTRACE_SINGLE_USER', '').strip().lower() in {'true', '1', 'yes'}


def access_policy() -> dict:
    # 明确返回实际策略，避免平台残留的旧配额变量被误认为仍生效。
    personal = single_user_enabled()
    return {'access_mode': 'single_user' if personal else 'organization',
            'authentication_required': not personal and os.getenv('AUDITTRACE_PUBLIC_DEMO', '').lower() in {'true', '1', 'yes'},
            'usage_quotas_enabled': not personal,
            'daily_token_limit': None if personal else 'configured',
            'daily_run_limit': None if personal else 'configured',
            'request_frequency_limit': None if personal else 'configured'}

"""把自动化测试日志与可供人工复核的开发运行记录隔离。"""

import os
import ipaddress
import socket

import pytest


os.environ["AUDITTRACE_RUNTIME_NAMESPACE"] = "pytest"


@pytest.fixture(autouse=True)
def forbid_external_test_connections(monkeypatch):
    """自动测试只能用内存提供方或本机服务，失配时阻断真实模型与案例外发。"""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def is_local(address):
        if not isinstance(address, tuple):
            return True
        host = str(address[0])
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def connect(sock, address):
        if not is_local(address):
            raise PermissionError("自动测试禁止外部网络连接，请注入离线提供方。")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if not is_local(address):
            raise PermissionError("自动测试禁止外部网络连接，请注入离线提供方。")
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)

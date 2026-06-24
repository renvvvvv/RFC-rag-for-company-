#!/usr/bin/env python3
"""
RAG 权限管理效果审计脚本
==============================
通过真实 HTTP 接口（默认经 Kong 网关）对五级权限体系进行端到端验证。
覆盖：API Key scope 边界、知识库/文档访问控制、PermissionService ACL、
用户群安全等级继承、管理员端点授权、认证边界、安全网关策略。

运行方式：
    python scripts/permission_audit.py [--base-url http://localhost:8000] [--admin-password Admin123!]

输出：
    scripts/reports/permission_audit_report.json
    scripts/reports/permission_audit_report.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


REPORT_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_BASE_URL = "http://localhost:8080"
ADMIN_USERNAME = "admin"
TEST_PASSWORD = "TestPass123!"


@dataclass
class TestResult:
    suite: str
    name: str
    passed: bool
    severity: str  # P0 / P1 / P2
    expected: str
    actual: str
    details: dict[str, Any] = field(default_factory=dict)


class PermissionAudit:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, admin_password: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.admin_password = admin_password or TEST_PASSWORD
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.results: list[TestResult] = []
        self.users: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, str] = {}
        self.api_keys: dict[str, dict[str, Any]] = {}
        self.admin_user: dict[str, Any] | None = None
        self.admin_token: str | None = None
        self.test_artifacts: dict[str, Any] = {"kbs": [], "docs": [], "groups": [], "permissions": []}

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def headers(self, token: str | None = None, api_key: str | None = None) -> dict[str, str]:
        h: dict[str, str] = {}
        if token:
            h["Authorization"] = f"Bearer {token}"
        if api_key:
            h["X-API-Key"] = api_key
        return h

    def _req(
        self,
        method: str,
        path: str,
        token: str | None = None,
        api_key: str | None = None,
        json_data: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_4xx: bool = True,
    ) -> requests.Response:
        """发起请求；4xx/5xx 直接返回，便于断言。"""
        try:
            resp = self.session.request(
                method=method,
                url=self.url(path),
                headers=self.headers(token, api_key),
                json=json_data,
                data=data,
                files=files,
                params=params,
                timeout=timeout,
            )
            return resp
        except requests.RequestException as exc:
            fake = requests.Response()
            fake.status_code = 0
            fake._content = json.dumps({"detail": f"RequestException: {exc}"}).encode()
            fake.headers["Content-Type"] = "application/json"
            return fake

    def _json(self, resp: requests.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text[:500]}

    def _add(
        self,
        suite: str,
        name: str,
        passed: bool,
        expected: str,
        actual: str,
        severity: str = "P1",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.results.append(
            TestResult(
                suite=suite,
                name=name,
                passed=passed,
                severity=severity,
                expected=expected,
                actual=actual,
                details=details or {},
            )
        )

    # ------------------------------------------------------------------ #
    # Setup / teardown
    # ------------------------------------------------------------------ #
    def setup(self) -> None:
        # 1) 确保 admin 账号可用（若已存在则尝试登录，失败则跳过管理员测试）
        self._ensure_admin()

        # 2) 创建 L0-L4 测试用户
        for level in ("L0", "L1", "L2", "L3", "L4"):
            self._register_user(level)

        # 3) 为每个用户创建 API Key（覆盖其允许的最大 scope）
        for level, user in self.users.items():
            self._create_api_key_for_user(level, user)

    def _ensure_admin(self) -> None:
        # 先尝试注册 admin
        resp = self._req(
            "POST",
            "/api/v1/auth/register",
            json_data={
                "username": ADMIN_USERNAME,
                "email": f"admin_{self.run_id}@example.com",
                "password": self.admin_password,
                "display_name": "Admin",
                "security_level": "L4",
            },
        )
        if resp.status_code in (200, 201):
            self.admin_user = self._json(resp)
        else:
            # 可能已存在，尝试登录
            login = self._req(
                "POST",
                "/api/v1/auth/login",
                data={"username": ADMIN_USERNAME, "password": self.admin_password},
            )
            if login.status_code == 200:
                self.admin_user = self._json(login)["user"]
                self.admin_token = self._json(login)["access_token"]
            else:
                self.admin_user = None
                self.admin_token = None
                return

        if self.admin_user and not self.admin_token:
            login = self._req(
                "POST",
                "/api/v1/auth/login",
                data={"username": ADMIN_USERNAME, "password": self.admin_password},
            )
            if login.status_code == 200:
                self.admin_token = self._json(login)["access_token"]

    def _register_user(self, level: str) -> None:
        username = f"perm_{level.lower()}_{self.run_id}"
        email = f"{username}@example.com"

        # Use admin endpoint if available so we can create L1-L4 test users.
        # Public registration now forces L0.
        if self.admin_token:
            resp = self._req(
                "POST",
                "/api/v1/users",
                token=self.admin_token,
                json_data={
                    "username": username,
                    "email": email,
                    "password": TEST_PASSWORD,
                    "display_name": f"Test {level}",
                    "security_level": level,
                },
            )
        else:
            # Fallback: public registration (will only produce L0 users)
            resp = self._req(
                "POST",
                "/api/v1/auth/register",
                json_data={
                    "username": username,
                    "email": email,
                    "password": TEST_PASSWORD,
                    "display_name": f"Test {level}",
                    "security_level": level,
                },
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to register {level}: {self._json(resp)}")
        user = self._json(resp)
        self.users[level] = user

        login = self._req(
            "POST",
            "/api/v1/auth/login",
            data={"username": username, "password": TEST_PASSWORD},
        )
        if login.status_code != 200:
            raise RuntimeError(f"Failed to login {level}: {self._json(login)}")
        self.tokens[level] = self._json(login)["access_token"]

    def _create_api_key_for_user(self, level: str, user: dict[str, Any]) -> None:
        scopes_by_level = {
            "L0": ["kb:read", "search", "chat"],
            "L1": ["kb:read", "search", "chat", "doc:write"],
            "L2": ["kb:read", "search", "chat", "doc:write", "kb:write"],
            "L3": ["kb:read", "search", "chat", "doc:write", "kb:write", "user:read", "apikey:admin"],
            "L4": ["*"],
        }
        resp = self._req(
            "POST",
            "/api/v1/api-keys",
            token=self.tokens[level],
            json_data={
                "name": f"max-scope-{level}",
                "scopes": scopes_by_level[level],
                "rate_limit_rpm": 1000,
            },
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Failed to create API key for {level}: {self._json(resp)}")
        data = self._json(resp)
        self.api_keys[level] = data

    def teardown(self) -> None:
        # 撤销 API Key、删除测试知识库/文档/用户群
        for level, key in self.api_keys.items():
            self._req(
                "DELETE",
                f"/api/v1/api-keys/{key['id']}",
                token=self.tokens.get(level),
            )
        for kb_id in self.test_artifacts.get("kbs", []):
            for level in ("L4", "L3", "L2"):
                resp = self._req(
                    "DELETE",
                    f"/api/v1/knowledge-bases/{kb_id}",
                    token=self.tokens.get(level),
                )
                if resp.status_code in (204, 200, 404):
                    break
        for group_id in self.test_artifacts.get("groups", []):
            if self.admin_token:
                self._req(
                    "DELETE",
                    f"/api/v1/groups/{group_id}",
                    token=self.admin_token,
                )
        # 测试用户无法自行删除；保留记录并在报告中说明

    # ------------------------------------------------------------------ #
    # Test suites
    # ------------------------------------------------------------------ #
    def run_api_key_scope_tests(self) -> None:
        suite = "API Key Scope Enforcement"

        # L0 不能创建超出自身等级的 key
        resp = self._req(
            "POST",
            "/api/v1/api-keys",
            token=self.tokens["L0"],
            json_data={"name": "escalation", "scopes": ["doc:write"]},
        )
        self._add(
            suite,
            "L0 cannot request doc:write scope",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code} {self._json(resp).get('detail', '')}",
            "P0",
        )

        # L1 不能请求 kb:write
        resp = self._req(
            "POST",
            "/api/v1/api-keys",
            token=self.tokens["L1"],
            json_data={"name": "escalation", "scopes": ["kb:write"]},
        )
        self._add(
            suite,
            "L1 cannot request kb:write scope",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code} {self._json(resp).get('detail', '')}",
            "P0",
        )

        # L4 可创建 * scope
        resp = self._req(
            "POST",
            "/api/v1/api-keys",
            token=self.tokens["L4"],
            json_data={"name": "wildcard", "scopes": ["*"]},
        )
        self._add(
            suite,
            "L4 can create wildcard scope key",
            resp.status_code == 201,
            "201 Created",
            f"{resp.status_code}",
            "P0",
            {"scopes": self._json(resp).get("scopes") if resp.status_code == 201 else None},
        )

        # 使用 L0 key 调用需要 doc:write 的上传接口应 403
        kb = self._create_kb("l1_owned_for_scope_test", "L1")
        fake_file = {"file": ("test.txt", b"hello", "text/plain")}
        resp = self._req(
            "POST",
            f"/api/v1/external/knowledge-bases/{kb['id']}/documents",
            api_key=self.api_keys["L0"]["plain_key"],
            data={"tags": ""},
            files=fake_file,
        )
        self._add(
            suite,
            "L0 key cannot call doc:write upload endpoint",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code} {self._json(resp).get('detail', '')}",
            "P0",
        )

        # 错误/过期 key 应 401
        resp = self._req(
            "GET",
            "/api/v1/external/knowledge-bases",
            api_key="rag_live_invalid_key_xxxx",
        )
        self._add(
            suite,
            "Invalid API key rejected",
            resp.status_code == 401,
            "401 Unauthorized",
            f"{resp.status_code}",
            "P0",
        )

        # 过期 key
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        resp = self._req(
            "POST",
            "/api/v1/api-keys",
            token=self.tokens["L2"],
            json_data={
                "name": "expired",
                "scopes": ["search"],
                "expires_at": yesterday.isoformat(),
            },
        )
        if resp.status_code == 201:
            expired_key = self._json(resp)["plain_key"]
            resp2 = self._req(
                "GET",
                "/api/v1/external/knowledge-bases",
                api_key=expired_key,
            )
            self._add(
                suite,
                "Expired API key rejected",
                resp2.status_code == 401,
                "401 Unauthorized",
                f"{resp2.status_code} {self._json(resp2).get('detail', '')}",
                "P0",
            )
        else:
            self._add(
                suite,
                "Expired API key rejected",
                False,
                "201 created expired key then 401 on use",
                f"Failed to create expired key: {resp.status_code} {self._json(resp)}",
                "P0",
            )

    def run_kb_access_tests(self) -> None:
        suite = "Knowledge Base Access Control"

        # L2 创建 KB
        kb = self._create_kb("owner_l2_kb", "L2")

        # 拥有者可访问
        resp = self._req(
            "GET",
            f"/api/v1/knowledge-bases/{kb['id']}",
            token=self.tokens["L2"],
        )
        self._add(
            suite,
            "KB owner can retrieve own KB",
            resp.status_code == 200,
            "200 OK",
            f"{resp.status_code}",
            "P0",
        )

        # 非拥有者（L1）应 403
        resp = self._req(
            "GET",
            f"/api/v1/knowledge-bases/{kb['id']}",
            token=self.tokens["L1"],
        )
        self._add(
            suite,
            "Non-owner cannot retrieve others KB",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

        # 非拥有者尝试修改应 403
        resp = self._req(
            "PATCH",
            f"/api/v1/knowledge-bases/{kb['id']}",
            token=self.tokens["L1"],
            json_data={"name": "hijacked"},
        )
        self._add(
            suite,
            "Non-owner cannot update others KB",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

        # 列表接口是否过滤？当前实现返回所有 KB，记录为问题
        resp = self._req(
            "GET",
            "/api/v1/knowledge-bases",
            token=self.tokens["L0"],
        )
        all_kbs = self._json(resp) if resp.status_code == 200 else []
        others_visible = any(str(k.get("id")) == str(kb["id"]) for k in all_kbs)
        self._add(
            suite,
            "KB list should not leak others KBs (known gap)",
            not others_visible,
            "L0 should not see L2's KB in list",
            f"visible={others_visible}, total={len(all_kbs)}",
            "P1",
        )

        # 外部 API：L2 key 可创建 KB
        resp = self._req(
            "POST",
            "/api/v1/external/knowledge-bases",
            api_key=self.api_keys["L2"]["plain_key"],
            json_data={"name": "external_kb_l2", "description": "via api key"},
        )
        self._add(
            suite,
            "L2 API key can create KB",
            resp.status_code == 201,
            "201 Created",
            f"{resp.status_code}",
            "P0",
        )

        # 外部 API：L1 key 创建 KB 应 403（缺少 kb:write）
        resp = self._req(
            "POST",
            "/api/v1/external/knowledge-bases",
            api_key=self.api_keys["L1"]["plain_key"],
            json_data={"name": "external_kb_l1", "description": "via api key"},
        )
        self._add(
            suite,
            "L1 API key cannot create KB",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

    def run_document_access_tests(self) -> None:
        suite = "Document Access Control"

        kb = self._create_kb("doc_perm_kb", "L2")
        doc = self._upload_doc(kb["id"], "L2", "shared_doc.txt", b"secret content")
        if not doc:
            self._add(
                suite,
                "Setup: upload document for access tests",
                False,
                "200/201",
                "upload failed",
                "P0",
            )
            return

        # 拥有者可查看
        resp = self._req(
            "GET",
            f"/api/v1/documents/detail/{doc['id']}",
            token=self.tokens["L2"],
        )
        self._add(
            suite,
            "KB owner can view document detail",
            resp.status_code == 200,
            "200 OK",
            f"{resp.status_code}",
            "P0",
        )

        # 非拥有者 detail 端点是否鉴权？当前实现未校验，属于漏洞
        resp = self._req(
            "GET",
            f"/api/v1/documents/detail/{doc['id']}",
            token=self.tokens["L0"],
        )
        self._add(
            suite,
            "Non-owner document detail should be denied (known gap)",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

        # 非拥有者 download 应 403
        resp = self._req(
            "GET",
            f"/api/v1/documents/detail/{doc['id']}/download",
            token=self.tokens["L0"],
        )
        self._add(
            suite,
            "Non-owner document download denied",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

        # 非拥有者 delete 是否鉴权？当前实现未校验
        another_doc = self._upload_doc(kb["id"], "L2", "victim_doc.txt", b"victim")
        if another_doc:
            resp = self._req(
                "DELETE",
                f"/api/v1/documents/detail/{another_doc['id']}",
                token=self.tokens["L0"],
            )
            self._add(
                suite,
                "Non-owner document delete should be denied (known gap)",
                resp.status_code == 403,
                "403 Forbidden",
                f"{resp.status_code}",
                "P0",
            )

    def run_permission_service_tests(self) -> None:
        suite = "PermissionService ACL"

        kb = self._create_kb("acl_kb", "L2")
        doc = self._upload_doc(kb["id"], "L2", "acl_doc.txt", b"acl content")
        if not doc:
            self._add(suite, "Setup ACL doc", False, "created", "upload failed", "P0")
            return

        l0_id = self.users["L0"]["id"]

        # 默认无显式权限
        resp = self._req(
            "GET",
            f"/api/v1/permissions/check/document/{doc['id']}",
            token=self.tokens["L0"],
        )
        data = self._json(resp)
        self._add(
            suite,
            "Default document permission is NONE",
            resp.status_code == 200 and data.get("permission") == "NONE",
            "200 OK permission=NONE",
            f"{resp.status_code} {data}",
            "P1",
        )

        # 授予 READ
        resp = self._req(
            "POST",
            "/api/v1/permissions/grant",
            token=self.tokens["L2"],
            json_data={
                "target_type": "user",
                "target_id": l0_id,
                "object_type": "document",
                "object_id": doc["id"],
                "permission": "READ",
            },
        )
        self._add(
            suite,
            "Grant READ on document",
            resp.status_code == 200,
            "200 OK",
            f"{resp.status_code}",
            "P1",
        )

        resp = self._req(
            "GET",
            f"/api/v1/permissions/check/document/{doc['id']}",
            token=self.tokens["L0"],
        )
        data = self._json(resp)
        self._add(
            suite,
            "After grant, permission is READ",
            resp.status_code == 200 and data.get("permission") == "READ",
            "200 OK permission=READ",
            f"{resp.status_code} {data}",
            "P1",
        )

        # 撤销
        resp = self._req(
            "POST",
            "/api/v1/permissions/revoke",
            token=self.tokens["L2"],
            json_data={
                "target_type": "user",
                "target_id": l0_id,
                "object_type": "document",
                "object_id": doc["id"],
            },
        )
        self._add(
            suite,
            "Revoke document permission",
            resp.status_code == 200,
            "200 OK",
            f"{resp.status_code}",
            "P1",
        )

        # 文件类型权限
        resp = self._req(
            "POST",
            "/api/v1/permissions/file-type",
            token=self.tokens["L2"],
            json_data={
                "target_type": "user",
                "target_id": l0_id,
                "file_type": "TEXT",
                "permissions": ["READ"],
            },
        )
        self._add(
            suite,
            "Grant file type READ",
            resp.status_code == 200,
            "200 OK",
            f"{resp.status_code}",
            "P1",
        )

        resp = self._req(
            "GET",
            "/api/v1/permissions/check/file_type/TEXT",
            token=self.tokens["L0"],
        )
        data = self._json(resp)
        self._add(
            suite,
            "File type check returns READ after grant",
            resp.status_code == 200 and data.get("permission") == "READ",
            "200 OK permission=READ",
            f"{resp.status_code} {data}",
            "P1",
        )

    def run_group_security_level_tests(self) -> None:
        suite = "User Group Security Level Inheritance"

        l1_id = self.users["L1"]["id"]
        l2_id = self.users["L2"]["id"]

        # 创建 max_security_level=L3 的群，并将 L1 加入
        resp = self._req(
            "POST",
            "/api/v1/groups",
            token=self.tokens["L2"],
            json_data={
                "name": f"high_level_group_{self.run_id}",
                "description": "group with L3 max",
                "max_security_level": "L3",
                "member_ids": [l1_id],
                "admin_ids": [l2_id],
            },
        )
        if resp.status_code not in (200, 201):
            self._add(suite, "Create test group", False, "200/201", f"{resp.status_code}", "P1")
            return
        group = self._json(resp)
        self.test_artifacts["groups"].append(group["id"])

        # L1 单独为 L1，但入群后 effective level 应为 L3
        resp = self._req(
            "GET",
            "/api/v1/permissions/check/file_type/ANY",
            token=self.tokens["L1"],
        )
        data = self._json(resp)
        self._add(
            suite,
            "Group max_security_level raises effective level",
            resp.status_code == 200 and data.get("security_level") == "L3",
            "200 OK security_level=L3",
            f"{resp.status_code} {data}",
            "P1",
        )

        # 用户群管理无权限校验：L0 也能修改任意群
        resp = self._req(
            "PUT",
            f"/api/v1/groups/{group['id']}",
            token=self.tokens["L0"],
            json_data={"name": f"hijacked_by_l0_{self.run_id}"},
        )
        self._add(
            suite,
            "Group update should require admin/owner (known gap)",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P1",
        )

    def run_admin_endpoint_tests(self) -> None:
        suite = "Admin Endpoint Authorization"

        if not self.admin_token:
            self._add(
                suite,
                "Admin credentials available",
                False,
                "admin logged in",
                "admin login/registration failed; admin endpoint tests skipped",
                "P1",
            )
            return

        # 管理员可列出用户
        resp = self._req("GET", "/api/v1/users", token=self.admin_token)
        self._add(
            suite,
            "Admin can list users",
            resp.status_code == 200,
            "200 OK",
            f"{resp.status_code}",
            "P0",
        )

        # 非管理员无法列出用户
        resp = self._req("GET", "/api/v1/users", token=self.tokens["L0"])
        self._add(
            suite,
            "Non-admin cannot list users",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

        # 非管理员无法删除他人
        victim_id = self.users["L0"]["id"]
        resp = self._req(
            "DELETE",
            f"/api/v1/users/{victim_id}",
            token=self.tokens["L1"],
        )
        self._add(
            suite,
            "Non-admin cannot delete user",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

    def run_security_gateway_tests(self) -> None:
        suite = "Security Gateway Strategy"

        # L4 用户发起 chat 应被 local_only 拦截（无论内容）
        # 需要先有知识库，但 chat 会在检测到 L4 时拦截；若无 KB 可能 422。
        kb = self._create_kb("gateway_kb", "L2")
        resp = self._req(
            "POST",
            "/api/v1/external/chat",
            api_key=self.api_keys["L4"]["plain_key"],
            json_data={
                "query": "hello",
                "kb_ids": [kb["id"]],
                "stream": False,
            },
            timeout=60,
        )
        data = self._json(resp)
        blocked = resp.status_code == 200 and "绝密" in str(data)
        self._add(
            suite,
            "L4 user query blocked by security gateway (local_only)",
            blocked,
            "200 with intercepted/local_only message",
            f"{resp.status_code} {data}",
            "P1",
        )

    def run_registration_escalation_tests(self) -> None:
        suite = "Registration Escalation"
        resp = self._req(
            "POST",
            "/api/v1/auth/register",
            json_data={
                "username": f"escalator_{self.run_id}",
                "email": f"escalator_{self.run_id}@example.com",
                "password": TEST_PASSWORD,
                "security_level": "L4",
            },
        )
        data = self._json(resp)
        level = data.get("security_level") if resp.status_code in (200, 201) else None
        self._add(
            suite,
            "Register with L4 security_level should be rejected or downgraded",
            resp.status_code not in (200, 201) or level != "L4",
            "400/403 or security_level != L4",
            f"{resp.status_code} security_level={level}",
            "P0",
        )

    def run_external_non_owner_tests(self) -> None:
        suite = "External API Non-owner Access"
        kb = self._create_kb("external_owner_kb", "L2")

        for path in [
            f"/api/v1/external/knowledge-bases/{kb['id']}",
            f"/api/v1/external/knowledge-bases/{kb['id']}/stats",
            f"/api/v1/external/knowledge-bases/{kb['id']}/documents",
        ]:
            resp = self._req("GET", path, api_key=self.api_keys["L0"]["plain_key"])
            self._add(
                suite,
                f"L0 key cannot access {path}",
                resp.status_code == 403,
                "403 Forbidden",
                f"{resp.status_code}",
                "P0",
            )

    def run_group_management_auth_tests(self) -> None:
        suite = "Group Management Authorization"
        l1_id = self.users["L1"]["id"]
        l0_id = self.users["L0"]["id"]

        resp = self._req(
            "POST",
            "/api/v1/groups",
            token=self.tokens["L2"],
            json_data={
                "name": f"protected_group_{self.run_id}",
                "max_security_level": "L2",
                "member_ids": [l1_id],
                "admin_ids": [l1_id],
            },
        )
        if resp.status_code not in (200, 201):
            self._add(suite, "Create test group", False, "200/201", f"{resp.status_code}", "P0")
            return
        group = self._json(resp)
        self.test_artifacts["groups"].append(group["id"])

        # 为不同操作创建独立群组，避免 DELETE 导致后续 404
        groups_for_ops = []
        for idx, (method, body) in enumerate([
            ("PUT", {"name": f"hijacked_{self.run_id}"}),
            ("DELETE", None),
            ("POST", {"user_ids": [l0_id]}),
            ("DELETE", {"user_ids": [l1_id]}),
        ]):
            resp = self._req(
                "POST",
                "/api/v1/groups",
                token=self.tokens["L2"],
                json_data={
                    "name": f"protected_group_{self.run_id}_{idx}",
                    "max_security_level": "L2",
                    "member_ids": [l1_id],
                    "admin_ids": [l1_id],
                },
            )
            if resp.status_code in (200, 201):
                g = self._json(resp)
                self.test_artifacts["groups"].append(g["id"])
                groups_for_ops.append((method, g["id"], body))

        for method, group_id, body in groups_for_ops:
            path = f"/api/v1/groups/{group_id}"
            if method in ("POST", "DELETE") and body is not None and "user_ids" in body:
                path = f"/api/v1/groups/{group_id}/members"
            resp = self._req(method, path, token=self.tokens["L0"], json_data=body)
            self._add(
                suite,
                f"L0 {method} group endpoint blocked",
                resp.status_code == 403,
                "403 Forbidden",
                f"{resp.status_code}",
                "P0",
            )

    def run_api_key_isolation_tests(self) -> None:
        suite = "API Key Isolation"
        l1_key = self.api_keys["L1"]

        # L2 不能列出 L1 的 key
        resp = self._req("GET", "/api/v1/api-keys", token=self.tokens["L2"])
        ids = {k["id"] for k in self._json(resp)} if resp.status_code == 200 else set()
        self._add(
            suite,
            "L2 cannot see L1's API key in list",
            l1_key["id"] not in ids,
            "L1 key id absent",
            f"present={l1_key['id'] in ids}",
            "P0",
        )

        # L2 不能撤销 L1 的 key
        resp = self._req(
            "DELETE",
            f"/api/v1/api-keys/{l1_key['id']}",
            token=self.tokens["L2"],
        )
        self._add(
            suite,
            "L2 cannot revoke L1's API key",
            resp.status_code in (403, 404),
            "403 or 404",
            f"{resp.status_code}",
            "P0",
        )

    def run_deny_priority_tests(self) -> None:
        suite = "ACL DENY Priority"
        kb = self._create_kb("deny_priority_kb", "L2")
        doc = self._upload_doc(kb["id"], "L2", "deny_doc.txt", b"deny test")
        if not doc:
            self._add(suite, "Setup deny test doc", False, "created", "upload failed", "P0")
            return

        l0_id = self.users["L0"]["id"]

        # 创建一个包含 L0 的群并授予 READ
        resp = self._req(
            "POST",
            "/api/v1/groups",
            token=self.tokens["L2"],
            json_data={
                "name": f"deny_group_{self.run_id}",
                "member_ids": [l0_id],
                "admin_ids": [l0_id],
            },
        )
        if resp.status_code not in (200, 201):
            self._add(suite, "Create group for deny test", False, "200/201", f"{resp.status_code}", "P0")
            return
        group = self._json(resp)
        self.test_artifacts["groups"].append(group["id"])

        self._req(
            "POST",
            "/api/v1/permissions/grant",
            token=self.tokens["L2"],
            json_data={
                "target_type": "group",
                "target_id": group["id"],
                "object_type": "document",
                "object_id": doc["id"],
                "permission": "READ",
            },
        )
        # 再给用户单独 DENY
        self._req(
            "POST",
            "/api/v1/permissions/grant",
            token=self.tokens["L2"],
            json_data={
                "target_type": "user",
                "target_id": l0_id,
                "object_type": "document",
                "object_id": doc["id"],
                "permission": "DENY",
            },
        )

        resp = self._req(
            "GET",
            f"/api/v1/permissions/check/document/{doc['id']}",
            token=self.tokens["L0"],
        )
        data = self._json(resp)
        self._add(
            suite,
            "User DENY overrides group READ",
            resp.status_code == 200 and data.get("permission") == "DENY",
            "200 OK permission=DENY",
            f"{resp.status_code} {data}",
            "P0",
        )

    def run_admin_endpoint_detail_tests(self) -> None:
        suite = "Admin Endpoint Detail Authorization"
        if not self.admin_token:
            self._add(suite, "Admin available", False, "yes", "no", "P0")
            return

        victim_id = self.users["L0"]["id"]
        l1_id = self.users["L1"]["id"]

        # 非管理员不能创建用户
        resp = self._req(
            "POST",
            "/api/v1/users",
            token=self.tokens["L1"],
            json_data={
                "username": f"created_by_l1_{self.run_id}",
                "email": f"created_by_l1_{self.run_id}@example.com",
                "password": TEST_PASSWORD,
                "security_level": "L0",
            },
        )
        self._add(
            suite,
            "Non-admin cannot create user via admin endpoint",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

        # 非管理员不能查看他人资料
        resp = self._req(
            "GET",
            f"/api/v1/users/{victim_id}",
            token=self.tokens["L1"],
        )
        self._add(
            suite,
            "Non-admin cannot view other user's profile",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

        # 本人可以查看自己
        resp = self._req(
            "GET",
            f"/api/v1/users/{l1_id}",
            token=self.tokens["L1"],
        )
        self._add(
            suite,
            "User can view own profile",
            resp.status_code == 200,
            "200 OK",
            f"{resp.status_code}",
            "P0",
        )

        # 非管理员不能修改他人
        resp = self._req(
            "PUT",
            f"/api/v1/users/{victim_id}",
            token=self.tokens["L1"],
            json_data={"display_name": "hijacked"},
        )
        self._add(
            suite,
            "Non-admin cannot update other user",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P0",
        )

    def run_scope_subset_tests(self) -> None:
        suite = "API Key Scope Subset Enforcement"
        # L2 创建仅含 kb:read 的 key
        resp = self._req(
            "POST",
            "/api/v1/api-keys",
            token=self.tokens["L2"],
            json_data={"name": "readonly", "scopes": ["kb:read"]},
        )
        if resp.status_code != 201:
            self._add(suite, "Create readonly key", False, "201", f"{resp.status_code}", "P1")
            return
        readonly_key = self._json(resp)["plain_key"]

        kb = self._create_kb("readonly_test_kb", "L2")
        resp = self._req(
            "POST",
            "/api/v1/external/knowledge-bases",
            api_key=readonly_key,
            json_data={"name": "attempt", "description": "x"},
        )
        self._add(
            suite,
            "kb:read-only key cannot create KB",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P1",
        )

        fake_file = {"file": ("test.txt", b"hello", "text/plain")}
        resp = self._req(
            "POST",
            f"/api/v1/external/knowledge-bases/{kb['id']}/documents",
            api_key=readonly_key,
            data={"tags": ""},
            files=fake_file,
        )
        self._add(
            suite,
            "kb:read-only key cannot upload document",
            resp.status_code == 403,
            "403 Forbidden",
            f"{resp.status_code}",
            "P1",
        )

    def run_rag_retrieval_permission_tests(self) -> None:
        suite = "RAG Retrieval Permission Filtering"
        kb = self._create_kb("rag_filter_kb", "L2")

        public_doc = self._upload_doc(kb["id"], "L2", "public_doc.txt", b"public information about project alpha")
        secret_doc = self._upload_doc(kb["id"], "L2", "secret_doc.txt", b"secret information about project alpha")

        if not public_doc or not secret_doc:
            self._add(suite, "Setup documents for RAG filter test", False, "created", "upload failed", "P0")
            return

        # Poll until documents are indexed
        ready = self._wait_for_docs([public_doc["id"], secret_doc["id"]], timeout=120)
        if not ready:
            self._add(
                suite,
                "Documents indexed within timeout",
                False,
                "completed",
                "indexing timeout",
                "P0",
            )
            return

        # Deny L0 access to secret_doc
        self._req(
            "POST",
            "/api/v1/permissions/grant",
            token=self.tokens["L2"],
            json_data={
                "target_type": "user",
                "target_id": self.users["L0"]["id"],
                "object_type": "document",
                "object_id": secret_doc["id"],
                "permission": "DENY",
            },
        )

        # Search as L0
        resp_l0 = self._req(
            "POST",
            "/api/v1/external/search",
            api_key=self.api_keys["L0"]["plain_key"],
            json_data={
                "query": "project alpha",
                "kb_ids": [kb["id"]],
                "top_k": 10,
                "rerank_top_k": 10,
            },
            timeout=120,
        )

        # Search as L2
        resp_l2 = self._req(
            "POST",
            "/api/v1/external/search",
            api_key=self.api_keys["L2"]["plain_key"],
            json_data={
                "query": "project alpha",
                "kb_ids": [kb["id"]],
                "top_k": 10,
                "rerank_top_k": 10,
            },
            timeout=120,
        )

        l0_doc_ids = {r.get("doc_id") for r in self._json(resp_l0).get("results", [])} if resp_l0.status_code == 200 else set()
        l2_doc_ids = {r.get("doc_id") for r in self._json(resp_l2).get("results", [])} if resp_l2.status_code == 200 else set()

        self._add(
            suite,
            "L0 search does not return denied secret_doc",
            resp_l0.status_code == 200 and str(secret_doc["id"]) not in l0_doc_ids,
            "200 OK and secret_doc absent",
            f"{resp_l0.status_code}, doc_ids={l0_doc_ids}",
            "P0",
        )
        self._add(
            suite,
            "L2 search can return both documents",
            resp_l2.status_code == 200 and str(secret_doc["id"]) in l2_doc_ids,
            "200 OK and secret_doc present",
            f"{resp_l2.status_code}, doc_ids={l2_doc_ids}",
            "P0",
        )
        self._add(
            suite,
            "Different accounts receive different RAG results",
            l0_doc_ids != l2_doc_ids,
            "result sets differ",
            f"L0={l0_doc_ids}, L2={l2_doc_ids}",
            "P0",
        )

    def _wait_for_docs(self, doc_ids: list[str], timeout: int = 120) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            all_ready = True
            for doc_id in doc_ids:
                resp = self._req(
                    "GET",
                    f"/api/v1/documents/detail/{doc_id}",
                    token=self.tokens["L2"],
                    timeout=10,
                )
                if resp.status_code != 200:
                    all_ready = False
                    break
                status = self._json(resp).get("status")
                if status not in ("indexed", "failed"):
                    all_ready = False
                    break
            if all_ready:
                return True
            time.sleep(3)
        return False

    def run_authentication_boundary_tests(self) -> None:
        suite = "Authentication Boundaries"

        # 错误密码
        resp = self._req(
            "POST",
            "/api/v1/auth/login",
            data={"username": self.users["L0"]["username"], "password": "wrongpass"},
        )
        self._add(
            suite,
            "Wrong password rejected",
            resp.status_code == 401,
            "401 Unauthorized",
            f"{resp.status_code}",
            "P0",
        )

        # 无效 JWT
        resp = self._req(
            "GET",
            "/api/v1/auth/me",
            token="invalid.token.here",
        )
        self._add(
            suite,
            "Invalid JWT rejected",
            resp.status_code == 401,
            "401 Unauthorized",
            f"{resp.status_code}",
            "P0",
        )

        # 禁用用户（管理员将 L0 设为 inactive）
        if self.admin_token:
            user_id = self.users["L0"]["id"]
            resp = self._req(
                "PUT",
                f"/api/v1/users/{user_id}",
                token=self.admin_token,
                json_data={"is_active": False},
            )
            if resp.status_code == 200:
                # 尝试登录
                resp2 = self._req(
                    "POST",
                    "/api/v1/auth/login",
                    data={"username": self.users["L0"]["username"], "password": TEST_PASSWORD},
                )
                self._add(
                    suite,
                    "Disabled user cannot login",
                    resp2.status_code == 401,
                    "401 Unauthorized",
                    f"{resp2.status_code}",
                    "P0",
                )
                # 禁用后 API Key 也应失效（认证时 load_owner 检查）
                resp3 = self._req(
                    "GET",
                    "/api/v1/external/knowledge-bases",
                    api_key=self.api_keys["L0"]["plain_key"],
                )
                self._add(
                    suite,
                    "API key of disabled owner rejected",
                    resp3.status_code == 401,
                    "401 Unauthorized",
                    f"{resp3.status_code}",
                    "P0",
                )
                # 恢复，避免影响后续测试
                self._req(
                    "PUT",
                    f"/api/v1/users/{user_id}",
                    token=self.admin_token,
                    json_data={"is_active": True},
                )
            else:
                self._add(
                    suite,
                    "Disable user via admin",
                    False,
                    "200 OK",
                    f"{resp.status_code}",
                    "P0",
                )

    # ------------------------------------------------------------------ #
    # Internal helpers for KB/doc creation
    # ------------------------------------------------------------------ #
    def _create_kb(self, name: str, owner_level: str) -> dict[str, Any]:
        kb_name = f"{name}_{self.run_id}"
        resp = self._req(
            "POST",
            "/api/v1/knowledge-bases",
            token=self.tokens[owner_level],
            json_data={"name": kb_name, "description": "permission audit kb"},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"KB creation failed: {self._json(resp)}")
        kb = self._json(resp)
        self.test_artifacts["kbs"].append(kb["id"])
        return kb

    def _upload_doc(
        self,
        kb_id: str,
        owner_level: str,
        filename: str,
        content: bytes,
    ) -> dict[str, Any] | None:
        resp = self._req(
            "POST",
            "/api/v1/documents",
            token=self.tokens[owner_level],
            data={"kb_id": kb_id, "tags": ""},
            files={"file": (filename, content, "text/plain")},
        )
        if resp.status_code in (200, 201):
            doc = self._json(resp)
            self.test_artifacts["docs"].append(doc["id"])
            return doc
        return None

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #
    def write_reports(self) -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        p0_failed = [r for r in self.results if r.severity == "P0" and not r.passed]

        report = {
            "metadata": {
                "base_url": self.base_url,
                "run_id": self.run_id,
                "started_at": datetime.now().isoformat(),
                "total": len(self.results),
                "passed": passed,
                "failed": failed,
                "p0_failed": len(p0_failed),
                "admin_available": self.admin_token is not None,
                "test_users": {k: str(v.get("id")) for k, v in self.users.items()},
            },
            "results": [
                {
                    "suite": r.suite,
                    "name": r.name,
                    "passed": r.passed,
                    "severity": r.severity,
                    "expected": r.expected,
                    "actual": r.actual,
                    "details": r.details,
                }
                for r in self.results
            ],
        }

        json_path = REPORT_DIR / f"permission_audit_report_{self.run_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        md_path = REPORT_DIR / f"permission_audit_report_{self.run_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# RAG 权限管理效果审计报告\n\n")
            f.write(f"- **测试时间**: {datetime.now().isoformat()}\n")
            f.write(f"- **目标服务**: {self.base_url}\n")
            f.write(f"- **总用例**: {len(self.results)}\n")
            f.write(f"- **通过**: {passed} ✅\n")
            f.write(f"- **失败**: {failed} ❌\n")
            f.write(f"- **P0 失败**: {len(p0_failed)} 🚨\n")
            f.write(f"- **管理员账号可用**: {'是' if self.admin_token else '否'}\n\n")

            if p0_failed:
                f.write("## P0 失败项（需立即修复）\n\n")
                for r in p0_failed:
                    f.write(f"### [{r.suite}] {r.name}\n")
                    f.write(f"- 期望: {r.expected}\n")
                    f.write(f"- 实际: {r.actual}\n\n")

            f.write("## 全部测试结果\n\n")
            f.write("| 套件 | 用例 | 级别 | 结果 | 期望 | 实际 |\n")
            f.write("|---|---|---|---|---|---|\n")
            for r in self.results:
                icon = "✅" if r.passed else "❌"
                f.write(f"| {r.suite} | {r.name} | {r.severity} | {icon} | {r.expected} | {r.actual} |\n")

            f.write("\n## 测试账号\n\n")
            for level, user in self.users.items():
                f.write(f"- **{level}**: `{user['username']}` / `{TEST_PASSWORD}` (id={user['id']})\n")

        print(f"Reports written to:\n  {json_path}\n  {md_path}")

    # ------------------------------------------------------------------ #
    # Main runner
    # ------------------------------------------------------------------ #
    def run(self) -> int:
        print(f"Starting permission audit against {self.base_url}")
        try:
            self.setup()
        except Exception as exc:
            print(f"Setup failed: {exc}")
            traceback.print_exc()
            return 2

        suites = [
            self.run_registration_escalation_tests,
            self.run_api_key_scope_tests,
            self.run_kb_access_tests,
            self.run_document_access_tests,
            self.run_external_non_owner_tests,
            self.run_permission_service_tests,
            self.run_group_security_level_tests,
            self.run_group_management_auth_tests,
            self.run_api_key_isolation_tests,
            self.run_deny_priority_tests,
            self.run_admin_endpoint_tests,
            self.run_admin_endpoint_detail_tests,
            self.run_scope_subset_tests,
            self.run_rag_retrieval_permission_tests,
            self.run_security_gateway_tests,
            self.run_authentication_boundary_tests,
        ]

        for suite in suites:
            try:
                suite()
            except Exception as exc:
                self._add(
                    "Runtime",
                    f"Suite {suite.__name__} crashed",
                    False,
                    "completed",
                    f"Exception: {exc}",
                    "P0",
                )
                traceback.print_exc()

        try:
            self.teardown()
        except Exception as exc:
            print(f"Teardown warning: {exc}")

        self.write_reports()
        failed = sum(1 for r in self.results if not r.passed)
        return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG permission management audit")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL of Kong gateway")
    parser.add_argument("--admin-password", default=None, help="Password for admin user if already exists")
    args = parser.parse_args()

    if not os.environ.get("PYTHONUNBUFFERED"):
        os.environ["PYTHONUNBUFFERED"] = "1"

    audit = PermissionAudit(base_url=args.base_url, admin_password=args.admin_password)
    return audit.run()


if __name__ == "__main__":
    sys.exit(main())

"""模型配置方案与「获取模型」相关能力的离线测试。

覆盖三类内容：
1. URL 归一化、响应解析等纯函数行为（不联网）；
2. fetch_model_ids 的请求构造与错误码映射（mock httpx，不联网）；
3. 仓库守卫：新增接口的明文约定、表单字段顺序，避免被后续改动无声破坏。
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from apps.system.crud import upstream_model
from apps.system.crud.upstream_model import (
    CODE_BAD_DOMAIN,
    CODE_EMPTY_DOMAIN,
    CODE_FORMAT,
    CODE_HTTP,
    CODE_TIMEOUT,
    UpstreamModelError,
    build_models_url,
    fetch_model_ids,
    normalize_base_url,
    parse_model_ids,
)

ROOT = Path(__file__).resolve().parent.parent.parent


class TestNormalizeBaseUrl(unittest.TestCase):
    def test_appends_v1_when_missing(self):
        self.assertEqual(
            normalize_base_url("https://api.hualong.online"), "https://api.hualong.online/v1"
        )

    def test_keeps_existing_v1(self):
        self.assertEqual(
            normalize_base_url("https://api.openai.com/v1"), "https://api.openai.com/v1"
        )

    def test_strips_trailing_slash(self):
        self.assertEqual(
            normalize_base_url("https://qianfan.baidubce.com/v2/"),
            "https://qianfan.baidubce.com/v2",
        )
        self.assertEqual(
            normalize_base_url("https://api.deepseek.com/v1///"),
            "https://api.deepseek.com/v1",
        )

    def test_build_models_url(self):
        self.assertEqual(
            build_models_url("https://api.hualong.online/"),
            "https://api.hualong.online/v1/models",
        )

    def test_preserves_provider_prefix(self):
        self.assertEqual(build_models_url("https://models.example.test/api/paas/v4/"),
                         "https://models.example.test/api/paas/v4/models")

    def test_rejects_embedded_credentials_and_parameters(self):
        for url in ("https://user:pass@models.test", "https://models.test?key=x", "https://models.test/#token", "http://"):
            with self.subTest(url=url), self.assertRaises(UpstreamModelError):
                normalize_base_url(url)

    def test_empty_domain(self):
        with self.assertRaises(UpstreamModelError) as ctx:
            normalize_base_url("   ")
        self.assertEqual(ctx.exception.code, CODE_EMPTY_DOMAIN)

    def test_requires_http_scheme(self):
        for bad in ("api.hualong.online", "ftp://api.hualong.online"):
            with self.assertRaises(UpstreamModelError) as ctx:
                normalize_base_url(bad)
            self.assertEqual(ctx.exception.code, CODE_BAD_DOMAIN)


class TestParseModelIds(unittest.TestCase):
    def test_extracts_sorted_unique_ids(self):
        payload = {
            "object": "list",
            "data": [
                {"id": "glm-5.3"},
                {"id": "gpt-4o-mini"},
                {"id": "glm-5.3"},
                {"id": ""},
                {"id": 123},
                "not-a-dict",
            ],
        }
        self.assertEqual(parse_model_ids(payload), ["glm-5.3", "gpt-4o-mini"])

    def test_empty_data_list(self):
        self.assertEqual(parse_model_ids({"data": []}), [])

    def test_rejects_non_object(self):
        with self.assertRaises(UpstreamModelError) as ctx:
            parse_model_ids([{"id": "x"}])
        self.assertEqual(ctx.exception.code, CODE_FORMAT)

    def test_rejects_missing_data(self):
        with self.assertRaises(UpstreamModelError) as ctx:
            parse_model_ids({"error": {"message": "invalid key"}})
        self.assertEqual(ctx.exception.code, CODE_FORMAT)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        self.calls.append({"url": url, "headers": headers})
        if self._error:
            raise self._error
        return self._response


class TestFetchModelIds(unittest.TestCase):
    def _patch_client(self, client):
        return patch.object(upstream_model.httpx, "Client", return_value=client)

    def test_success_sends_bearer_header(self):
        client = _FakeClient(_FakeResponse(payload={"data": [{"id": "glm-5.3"}]}))
        with self._patch_client(client):
            models = fetch_model_ids("https://api.hualong.online", "sk-test")
        self.assertEqual(models, ["glm-5.3"])
        self.assertEqual(client.calls[0]["url"], "https://api.hualong.online/v1/models")
        self.assertEqual(client.calls[0]["headers"], {"Authorization": "Bearer sk-test"})

    def test_no_key_omits_header(self):
        client = _FakeClient(_FakeResponse(payload={"data": []}))
        with self._patch_client(client):
            fetch_model_ids("https://api.hualong.online/v1", None)
        self.assertEqual(client.calls[0]["headers"], {})

    def test_http_error_keeps_status_code(self):
        client = _FakeClient(_FakeResponse(status_code=401, text='{"message":"bad key"}'))
        with self._patch_client(client), self.assertRaises(UpstreamModelError) as ctx:
            fetch_model_ids("https://api.hualong.online", "sk-wrong")
        self.assertEqual(ctx.exception.code, CODE_HTTP)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("bad key", ctx.exception.message)

    def test_timeout(self):
        client = _FakeClient(error=upstream_model.httpx.TimeoutException("slow"))
        with self._patch_client(client), self.assertRaises(UpstreamModelError) as ctx:
            fetch_model_ids("https://api.hualong.online", "sk-test")
        self.assertEqual(ctx.exception.code, CODE_TIMEOUT)

    def test_non_json_body(self):
        client = _FakeClient(_FakeResponse(text="<html>gateway</html>"))
        with self._patch_client(client), self.assertRaises(UpstreamModelError) as ctx:
            fetch_model_ids("https://api.hualong.online", "sk-test")
        self.assertEqual(ctx.exception.code, CODE_FORMAT)


class TestRepoGuards(unittest.TestCase):
    """源码级守卫：模型表单必须「先填地址密钥、再取模型」。"""

    def setUp(self):
        self.form = (ROOT / "frontend" / "src" / "views" / "system" / "model" / "ModelForm.vue").read_text(
            encoding="utf-8"
        )
        self.api = (ROOT / "frontend" / "src" / "api" / "system.ts").read_text(encoding="utf-8")
        self.router = (ROOT / "backend" / "apps" / "system" / "api" / "aimodel.py").read_text(
            encoding="utf-8"
        )

    def test_fetch_models_endpoint_is_plaintext_on_frontend(self):
        self.assertIn("'/system/aimodel/models'", self.api)
        fetch_block = self.api.split("fetchModels:", 1)[1].split("presetList", 1)[0]
        self.assertNotIn("sqlbotEncrypt", fetch_block)

    def test_api_domain_and_key_precede_base_model(self):
        form_items = self.form.split("<el-form-item", 1)[1]
        domain_pos = form_items.index('prop="api_domain"')
        key_pos = form_items.index('prop="api_key"')
        base_pos = form_items.index('prop="base_model"')
        self.assertLess(domain_pos, base_pos)
        self.assertLess(key_pos, base_pos)
        # 域名与密钥不再受「已选基础模型」门控
        self.assertNotIn('v-if="modelSelected" prop="api_domain"', self.form)
        self.assertNotIn('v-if="modelSelected" prop="api_key"', self.form)

    def test_form_offers_fetch_models_button(self):
        self.assertIn("@click=\"fetchModels\"", self.form)
        self.assertIn("remoteModelList", self.form)

    def test_backend_preset_routes_registered_before_id_route(self):
        preset_pos = self.router.index('@router.get("/preset"')
        id_pos = self.router.index('@router.get("/{id}"')
        self.assertLess(preset_pos, id_pos)

    def test_fetch_models_is_admin_only_and_not_auto_documented(self):
        self.assertIn('@router.post("/models", include_in_schema=False)', self.router)
        block = self.router.split('@router.post("/models"', 1)[1].split('@router.get("/preset"', 1)[0]
        self.assertIn("role=['admin']", block)


if __name__ == "__main__":
    unittest.main()

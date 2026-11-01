"""模型供应商配置的仓库守卫测试。

历史实现把 13 家厂商的服务地址、模型清单和默认参数写死在前端 `supplier.ts`，
新增或更换一个中转站都要改前端代码。当前实现只保留一个「OpenAI 兼容」通用供应商，
模型清单改为在表单里按「服务地址 + 密钥」实时拉取，本文件锁住这一设计不被回退。
"""

import json
import os
import pathlib
import re
import unittest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def _read(*parts):
    with open(os.path.join(PROJECT_ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class TestSingleGenericSupplier(unittest.TestCase):
    """supplier.ts 只应保留一个通用供应商。"""

    def setUp(self):
        self.content = _read("frontend", "src", "entity", "supplier.ts")

    def test_only_one_supplier_entry(self):
        """列表里只有一个供应商，且不再出现任何写死的数字 id 之外的厂商条目。"""
        self.assertEqual(self.content.count("id: GENERIC_SUPPLIER_ID"), 1)
        self.assertEqual(re.findall(r"\bid:\s*(\d+),", self.content), [])

    def test_generic_supplier_uses_openai_protocol(self):
        self.assertIn("export const GENERIC_SUPPLIER_ID = 15", self.content)
        self.assertIn("type: 'openai'", self.content)

    def test_no_hardcoded_model_options(self):
        """模型清单必须为空，由服务端按地址+密钥实时拉取。"""
        self.assertIn("model_options: []", self.content)
        self.assertEqual(
            re.findall(r"name: '(gpt-[^']+|o1[^']*|MiniMax[^']*)'", self.content), []
        )

    def test_no_vendor_icon_imports(self):
        """不再引入各厂商图标，避免把供应商清单写回前端。"""
        imports = re.findall(r"^import .* from '@/assets/model/.*$", self.content, re.M)
        self.assertEqual(len(imports), 1, imports)
        self.assertIn("icon_common_openai", imports[0])

    def test_get_supplier_falls_back_to_generic(self):
        """历史数据的旧 supplier id 需要回落到通用供应商，避免卡片空白。"""
        self.assertIn("|| supplierList[0]", self.content)

    def test_default_args_present_for_advanced_settings(self):
        self.assertIn("common_args", self.content)
        self.assertIn("temperature", self.content)


class TestSupplierChooserRemoved(unittest.TestCase):
    """供应商选择组件与相关入口必须保持删除状态。"""

    def test_chooser_components_removed(self):
        model_dir = os.path.join(PROJECT_ROOT, "frontend", "src", "views", "system", "model")
        for name in ("ModelList.vue", "ModelListSide.vue"):
            self.assertFalse(
                os.path.exists(os.path.join(model_dir, name)),
                f"{name} 应保持删除（供应商选择已下线）",
            )

    def test_model_view_has_no_supplier_step(self):
        content = _read("frontend", "src", "views", "system", "model", "Model.vue")
        self.assertNotIn("from './ModelList.vue'", content)
        self.assertNotIn("from './ModelListSide.vue'", content)
        self.assertNotIn("<ModelList", content)
        self.assertNotIn("supplierChang", content)
        self.assertNotIn("activeStep", content)
        self.assertIn("modelFormRef", content)

    def test_model_form_drops_supplier_plumbing(self):
        content = _read("frontend", "src", "views", "system", "model", "ModelForm.vue")
        for token in ("base_model_options", "modelTypeOptions", "tempConfigMap", "supplierChang"):
            self.assertNotIn(token, content)
        self.assertIn("GENERIC_SUPPLIER_ID", content)
        self.assertIn('@click="fetchModels"', content)


class TestSupplierI18nKeysRemoved(unittest.TestCase):
    """supplier.* 文案已无引用，应在所有 locale 中同步移除。"""

    def _load_locale(self, locale_name):
        return json.loads(_read("frontend", "src", "i18n", f"{locale_name}.json"))

    def test_supplier_block_removed(self):
        self.assertNotIn("supplier", self._load_locale("zh-CN"))

    def test_only_chinese_locales_shipped(self):
        """只保留简体中文：前端与后端都不再有多语言包。"""
        frontend = pathlib.Path(PROJECT_ROOT, "frontend", "src", "i18n")
        backend = pathlib.Path(PROJECT_ROOT, "backend", "locales")
        self.assertEqual(sorted(p.stem for p in frontend.glob("*.json")), ["zh-CN"])
        self.assertEqual(sorted(p.stem for p in backend.glob("*.json")), ["zh-CN"])

    def test_model_keys_present(self):
        keys = set(self._load_locale("zh-CN")["model"].keys())
        for key in ("fetch_models", "test_connection", "save_as_preset", "preset_section_title"):
            self.assertIn(key, keys)


class TestGenericProviderBackendSupport(unittest.TestCase):
    """后端应按 protocol 选择客户端，与前端供应商解耦。"""

    def setUp(self):
        self.factory_content = _read("backend", "apps", "ai_model", "model_factory.py")

    def test_openai_type_in_factory(self):
        self.assertIn('"openai"', self.factory_content)

    def test_factory_supports_register(self):
        self.assertIn("register_llm", self.factory_content)

    def test_openai_type_maps_to_openai_llm(self):
        self.assertIn('"openai": OpenAILLM', self.factory_content)

    def test_llm_config_has_api_base_url(self):
        self.assertIn("api_base_url", self.factory_content)

    def test_protocol_selects_client(self):
        """protocol=1 走 openai，protocol=2 走 vllm；不依赖 supplier。"""
        self.assertIn('"openai" if db_model.protocol == 1 else "vllm"', self.factory_content)


if __name__ == "__main__":
    unittest.main()

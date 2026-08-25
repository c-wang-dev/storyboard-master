"""解析器归一化单元测试（纯规则、零 API、离线可跑）。

覆盖优化1：content_type 六类标准集归一化 + move_purpose 同义词归一化。
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from storyboard import parser  # noqa: E402


class TestNormalizeContentType(unittest.TestCase):
    def test_standard_six(self):
        for ct in ["对白", "动作", "情绪", "环境", "悬念", "揭示"]:
            self.assertEqual(parser._normalize_content_type(ct), ct)

    def test_synonyms(self):
        cases = {
            "对话": "对白", "台词": "对白", "文戏": "对白",
            "打斗": "动作", "战斗": "动作", "冲突": "动作", "追击": "动作", "高潮": "动作", "爆发": "动作",
            "心理": "情绪", "内心": "情绪", "情绪戏": "情绪",
            "空镜": "环境", "场景": "环境", "氛围": "环境",
            "蓄力": "悬念", "铺垫": "悬念", "蓄势": "悬念",
            "揭晓": "揭示", "转折": "揭示", "反转": "揭示", "真相": "揭示",
        }
        for raw, want in cases.items():
            self.assertEqual(parser._normalize_content_type(raw), want, f"{raw} 应归一化为 {want}")

    def test_compound_takes_leading_word(self):
        # 复合类型取主导词（prompt 已要求主导唯一，此处兜底）
        self.assertEqual(parser._normalize_content_type("动作收束+对白"), "动作")
        self.assertEqual(parser._normalize_content_type("对白+动作"), "对白")

    def test_unknown_fallback(self):
        self.assertEqual(parser._normalize_content_type(""), "动作")
        self.assertEqual(parser._normalize_content_type("未知词汇"), "动作")


class TestNormalizeFeatures(unittest.TestCase):
    def test_suspense_scene_closed_loop(self):
        """悬念场景：move_purpose='蓄势' 应归一化为'聚焦'（否则运镜查空）。"""
        raw = {"content_type": "悬念蓄力", "info_focus": "细节", "emotion": "紧张",
               "power": "弱势", "move_purpose": "蓄势", "emotion_tone": "威胁",
               "pace": "慢", "info_point_count": "2"}
        f = parser._normalize_features(raw)
        self.assertEqual(f["content_type"], "悬念")
        self.assertEqual(f["move_purpose"], "聚焦")
        self.assertEqual(f["info_focus"], "细节")

    def test_info_point_count_coerce(self):
        f = parser._normalize_features({"info_point_count": "abc"})
        self.assertEqual(f["info_point_count"], 2)

    def test_dialogue_conclusion_scene(self):
        """片段4：动作收束+对白，LLM 应输出主导'对白'。"""
        raw = {"content_type": "对白", "move_purpose": "对峙", "emotion": "紧张"}
        f = parser._normalize_features(raw)
        self.assertEqual(f["content_type"], "对白")
        self.assertEqual(f["move_purpose"], "对峙")


if __name__ == "__main__":
    unittest.main()

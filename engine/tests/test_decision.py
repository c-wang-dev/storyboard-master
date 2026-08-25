"""决策引擎单元测试（纯规则、零 API、离线可跑）。"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from storyboard import decision, knowledge  # noqa: E402

KB_DIR = pathlib.Path(__file__).resolve().parents[2] / "knowledge"


class TestKnowledgeLoading(unittest.TestCase):
    def test_decision_tables_loaded(self):
        kb = knowledge.load_decision_tables(KB_DIR)
        self.assertIn("shot", kb["tables"])
        self.assertIn("angle", kb["tables"])
        self.assertIn("move", kb["tables"])
        self.assertIn("light", kb["tables"])
        self.assertIn("rhythm", kb["tables"])
        self.assertTrue(kb["tables"]["shot"], "景别表不应为空")
        self.assertEqual(kb["arbitration"], ["emotion", "info", "power"])

    def test_model_cards_loaded(self):
        cards = knowledge.load_model_cards(KB_DIR)
        self.assertGreaterEqual(len(cards), 6, "应有 6 张模型卡")
        self.assertIn("G1", cards)
        self.assertIn("G2", cards)
        self.assertIn("V1", cards)

    def test_negative_lists(self):
        kb = knowledge.load_decision_tables(KB_DIR)
        self.assertTrue(kb["negative_a"], "A 层负面词不应为空")
        self.assertTrue(kb["negative_b"], "B 层决策规避不应为空")


class TestDecisionEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = knowledge.load_decision_tables(KB_DIR)

    def test_shot_by_info_focus(self):
        # 环境 → 远景
        p = decision.decide({"info_focus": "环境", "content_type": "环境",
                             "emotion": "平静", "power": "对等",
                             "move_purpose": "关联", "emotion_tone": "压抑", "pace": "慢"},
                            self.kb)
        self.assertIn("远景", p["景别"])

    def test_angle_by_power(self):
        p = decision.decide({"info_focus": "关系", "content_type": "对白",
                             "emotion": "平静", "power": "强势",
                             "move_purpose": "对峙", "emotion_tone": "压抑", "pace": "慢"},
                            self.kb)
        self.assertIn("仰拍", p["角度"])

    def test_emotion_overrides_info(self):
        # 仲裁：情绪(爆发) > 信息(环境→远景)。应被覆盖为近景/特写
        p = decision.decide({"info_focus": "环境", "content_type": "动作",
                             "emotion": "爆发", "power": "强势",
                             "move_purpose": "聚焦", "emotion_tone": "压抑", "pace": "快"},
                            self.kb)
        self.assertIn("近景", p["景别"])

    def test_deterministic(self):
        """同样输入永远同样输出（核心卖点）。"""
        feats = {"info_focus": "情绪", "content_type": "对白", "emotion": "紧张",
                 "power": "弱势", "move_purpose": "聚焦", "emotion_tone": "神秘", "pace": "慢"}
        a = decision.decide(feats, self.kb)
        b = decision.decide(feats, self.kb)
        self.assertEqual(a, b)

    def test_duration_selection(self):
        self.assertEqual(decision.select_duration(1), "5s")
        self.assertEqual(decision.select_duration(2), "10s")
        self.assertEqual(decision.select_duration(5), "15s")

    def test_keyframes_counts(self):
        self.assertEqual(decision.count_keyframes("5s", "慢", "固定机位"), 1)
        k = decision.count_keyframes("15s", "快", "跟 / 移")
        self.assertGreaterEqual(k, 5)
        self.assertLessEqual(k, 20)


if __name__ == "__main__":
    unittest.main()

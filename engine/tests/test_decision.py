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

    def test_shot_relation_maps_to_mid(self):
        """info_focus=关系 应命中中景（双人关系），而非全景（曾被"环境关系"抢先匹配）。"""
        p = decision.decide({"info_focus": "关系", "content_type": "对白",
                             "emotion": "平静", "power": "对等",
                             "move_purpose": "对峙", "emotion_tone": "压抑", "pace": "慢"},
                            self.kb)
        self.assertIn("中景", p["景别"])

    def test_full_six_dim_no_none(self):
        """六维所有候选值查表均不应返回 None（防决策表关键词改动导致的查空回归）。"""
        info_focus = ["环境", "关系", "动作", "情绪", "细节"]
        powers = ["强势", "弱势", "对等", "主观", "失衡"]
        moves = ["追击", "聚焦", "离开", "关联", "不安", "对峙"]
        tones = ["压抑", "希望", "神秘", "悲怆", "威胁"]
        content_types = ["对白", "动作", "情绪", "环境", "悬念", "揭示"]
        for if_ in info_focus:
            for ct in content_types:
                feats = {"info_focus": if_, "content_type": ct,
                         "emotion": "平静", "power": "对等", "move_purpose": "对峙",
                         "emotion_tone": "神秘", "pace": "中"}
                p = decision.decide(feats, self.kb)
                for key in ("景别", "角度", "运镜", "光影", "节奏"):
                    self.assertIsNotNone(p.get(key), f"{if_}/{ct} 下 {key} 查空")
        for pw in powers:
            p = decision.decide({"info_focus": "关系", "content_type": "对白", "emotion": "平静",
                                 "power": pw, "move_purpose": "对峙", "emotion_tone": "神秘", "pace": "中"},
                                self.kb)
            self.assertIsNotNone(p.get("角度"), f"power={pw} 角度查空")
        for mv in moves:
            p = decision.decide({"info_focus": "关系", "content_type": "对白", "emotion": "平静",
                                 "power": "对等", "move_purpose": mv, "emotion_tone": "神秘", "pace": "中"},
                                self.kb)
            self.assertIsNotNone(p.get("运镜"), f"move={mv} 运镜查空")
        for tn in tones:
            p = decision.decide({"info_focus": "关系", "content_type": "对白", "emotion": "平静",
                                 "power": "对等", "move_purpose": "对峙", "emotion_tone": tn, "pace": "中"},
                                self.kb)
            self.assertIsNotNone(p.get("光影"), f"tone={tn} 光影查空")

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

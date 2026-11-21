"""Personal adaptation (Stage 4): the Python maths equals web/src/personal.js (same case as
web/tests/personal.test.mjs) and the measurement helper behaves."""

import unittest

import numpy as np

from tools.psl_train import personal


class PersonalTests(unittest.TestCase):
    def test_same_numbers_as_the_web(self):
        bias = personal.learn(np.zeros(3), np.log(np.array([0.6, 0.3, 0.1])), 1)
        np.testing.assert_allclose(bias, [-0.06, 0.07, -0.01], atol=1e-3)

    def toy(self, confidence):
        rng = np.random.default_rng(0)
        labels = rng.integers(0, 4, 300)
        p = np.full((300, 4), (1 - confidence) / 3)
        p[np.arange(300), labels] = confidence
        mine = labels == 2  # this person's sign 2 looks like sign 3 to the model
        p[mine] = [0.1, 0.1, 0.3, 0.5]
        return np.log(p), labels

    def test_helps_a_confident_model_and_never_hurts_an_unsure_one(self):
        for confidence, must_improve in ((0.9, True), (0.35, False)):
            scores, labels = self.toy(confidence)
            result = personal.measure(scores, labels, np.zeros(300, dtype=int), confirmations=20, repeats=10)
            self.assertGreaterEqual(result["worst_change_points"], 0.0, confidence)
            if must_improve:
                self.assertGreater(result["top1_after"], result["top1_before"])


if __name__ == "__main__":
    unittest.main()

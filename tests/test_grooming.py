"""Measured-source integrity, gate causality, and actual MuJoCo actuation."""
from pathlib import Path
import unittest

import mujoco
import numpy as np

from fruitfly.grooming import (GroomingPlayback, ReplayConfig, load_trace,
                               source_joint_map, audit_foreleg_forward_kinematics)

SOURCE = Path(__file__).resolve().parents[1] / "data/grooming/unilateral_left.npz"


class MeasuredTraceTests(unittest.TestCase):
    def test_pinned_trace_and_rejected_ik_outliers(self):
        trace = load_trace(SOURCE)
        self.assertEqual(len(trace["frame"]), 51)
        self.assertEqual(int(trace["frame"][0]), 4939)
        self.assertAlmostEqual(float(trace["time_relative_s"][-1]), .5)
        for name in ("figure1c_2to5s", "bilateral"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "IK outlier guard"):
                load_trace(SOURCE.with_name(name + ".npz"))

    def test_axis_mapping_checked_against_independent_source_markers(self):
        result = audit_foreleg_forward_kinematics(SOURCE)
        actual = result["documented_axis_map"]["rms_euclidean_error_mm"]
        control = result["no_right_axis_correction_control"]["rms_euclidean_error_mm"]
        # Source marker positions are independent of the target actuator output.
        # Current body geometry differs, so this is a bounded conversion audit.
        self.assertLess(actual, .065)
        self.assertGreater(control, .3)
        self.assertGreater(control / actual, 5)


class PlaybackGateTests(unittest.TestCase):
    def setUp(self):
        self.player = GroomingPlayback(SOURCE, np.zeros(len(source_joint_map())))
        self.current = self.player.neutral.copy()

    def advance(self, request, duration):
        for _ in range(round(duration / .01)):
            target = self.player.step(request, self.current, .01)
            if target is not None:
                self.current = target

    def test_tonic_gate_completes_once_and_requires_withdrawal(self):
        self.advance(True, 2)
        self.assertEqual(self.player.phase, "held")
        self.assertEqual(self.player.completed_count, 1)
        self.assertFalse(self.player.active)
        self.assertFalse(self.player.armed)
        np.testing.assert_allclose(self.current, self.player.neutral)
        self.advance(False, .01)
        self.assertEqual(self.player.phase, "ready")
        self.advance(True, 1.1)
        self.assertEqual(self.player.completed_count, 2)

    def test_withdrawal_cancels_and_blends_from_current_target(self):
        self.advance(True, .35)
        self.assertEqual(self.player.phase, "playing")
        before = self.current.copy()
        target = self.player.step(False, before, 1e-4)
        self.assertEqual(self.player.phase, "exiting")
        self.assertLess(float(np.max(np.abs(target-before))), 1e-5)
        self.current = target
        self.advance(False, .3)
        self.assertEqual(self.player.phase, "ready")
        self.assertEqual(self.player.completed_count, 0)
        self.assertEqual(self.player.cancelled_count, 1)
        np.testing.assert_allclose(self.current, self.player.neutral)

    def test_early_reassertion_during_exit_cannot_queue_restart(self):
        self.advance(True, .3)
        self.advance(False, .01)
        self.advance(True, 2)
        self.assertEqual(self.player.phase, "held")
        self.assertEqual(self.player.completed_count, 0)
        self.assertEqual(self.player.cancelled_count, 1)
        self.player.reset()
        self.assertEqual(self.player.phase, "ready")
        self.assertEqual(self.player.cancelled_count, 0)


class GroomingPhysicsTests(unittest.TestCase):
    def test_default_remains_walking_composition(self):
        from fruitfly.body import BodyRuntime
        with BodyRuntime(seed=11) as body:
            self.assertEqual(len(body._position_actuator_ids), 42)
            self.assertEqual(len(body._head_position_actuator_ids), 0)
            self.assertEqual(body.model.nu, 48)
            self.assertFalse(body.observe()["grooming"]["enabled"])
            with self.assertRaisesRegex(ValueError, "enable_grooming"):
                body.advance(.01, behavior="groom")
            observed = body.advance(.02, behavior="walk")
            self.assertEqual(observed["motor"]["mode"], "walk")
            self.assertTrue(np.isfinite(body.data.qpos).all())

    def test_body_gate_drives_physical_contacts_and_stops(self):
        from fruitfly.body import BodyConfig, BodyRuntime
        with BodyRuntime(seed=11, config=BodyConfig(enable_grooming=True)) as body:
            self.assertEqual(len(body._position_actuator_ids), 42)
            self.assertEqual(len(body._head_position_actuator_ids), 2)
            self.assertEqual(len(body._grooming_pair_labels), 72)
            no_gate = body.advance(.1, behavior="rest")
            self.assertEqual(no_gate["grooming"]["contact_s"], 0)
            active = body.advance(.3, behavior="groom")
            self.assertGreater(active["grooming"]["contact_count"], 0)
            # Contact telemetry is independently checked against actual MuJoCo
            # constraints; it is never manufactured from source activity labels.
            sums = np.zeros(72)
            wrench = np.zeros(6)
            for i in range(body.data.ncon):
                c = body.data.contact[i]
                pair = body._grooming_pair_lookup[c.geom1, c.geom2]
                if pair >= 0 and c.exclude == 0:
                    mujoco.mj_contactForce(body.model, body.data, i, wrench)
                    sums[pair] += max(float(wrench[0]), 0)
            np.testing.assert_array_equal(sums, body._grooming_contact_force)
            observed = body.advance(.45, behavior="groom")
            g = observed["grooming"]
            self.assertEqual(g["completed_count"], 1)
            self.assertGreater(g["contact_s"], .1)
            self.assertLess(g["tracking_rms_deg"], 3)
            self.assertLess(g["tracking_max_deg"], 15)
            self.assertEqual(g["tracking_sample_count"], 5000)
            forces = np.asarray(observed["proprioception"]["ground_force_by_leg"])
            self.assertTrue(np.all(forces[[1,2,4,5], 2] > 20))
            self.assertGreater(observed["pose"]["position_mm"][2], .8)
            held = body.advance(.7, behavior="groom")
            self.assertEqual(held["grooming"]["state"], "held")
            self.assertEqual(held["grooming"]["completed_count"], 1)
            self.assertEqual(held["grooming"]["contact_count"], 0)
            self.assertEqual(held["motor"]["mode"], "rest")
            # Head wind basis still tracks the articulated physical head and
            # remains a finite sensor observation after optional composition.
            self.assertTrue(np.isfinite(body.data.qvel).all())
            self.assertIsInstance(held["wind"], dict)
            body.reset(seed=11)
            self.assertEqual(body.observe()["grooming"]["contact_s"], 0)
            body.advance(.35, behavior="groom")
            withdrawn = body.advance(.4, behavior="rest")
            self.assertEqual(withdrawn["grooming"]["completed_count"], 0)
            self.assertEqual(withdrawn["grooming"]["cancelled_count"], 1)
            self.assertEqual(withdrawn["motor"]["mode"], "rest")
            body.advance(.3, behavior="walk")
            self.assertTrue(np.isfinite(body.data.qpos).all())
            self.assertGreater(body.observe()["pose"]["position_mm"][2], .6)


if __name__ == "__main__":
    unittest.main()

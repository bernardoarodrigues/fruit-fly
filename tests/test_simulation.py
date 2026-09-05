from pathlib import Path
import numpy as np
import pytest
from fruitfly.simulation import SimulationRunner


def test_coupling_rejects_fractional_neural_or_body_timesteps():
    with pytest.raises(ValueError, match="integer multiple"):
        SimulationRunner._require_multiple(.00015, .0001, "Coupling", "integration step")


@pytest.mark.skipif(not Path("data/processed/malecns_v1/manifest.json").exists(),
                    reason="Full MaleCNS validation requires explicitly downloaded graph")
def test_full_graph_reset_chunking_and_paused_observation(tmp_path):
    runner = SimulationRunner({"seed": 17, "run_dir": str(tmp_path), "assay": "motor_probe"})
    try:
        first = runner.advance(.04)
        qpos, voltage = runner.body.data.qpos.copy(), runner.brain.voltage_mv.copy()
        paused = runner.advance(0)
        assert paused["t_s"] == first["t_s"]
        assert paused["neural"]["spikes"] == first["neural"]["spikes"]
        runner.control({"type": "reset"})
        for _ in range(4):
            second = runner.advance(.01)
        np.testing.assert_array_equal(runner.body.data.qpos, qpos)
        np.testing.assert_array_equal(runner.brain.voltage_mv, voltage)
        assert second["neural"]["total_spikes"] == first["neural"]["total_spikes"]
        assert second["brain_t_s"] == pytest.approx(second["t_s"], abs=1e-12)
        assert second["neural"]["neurons"] == 166700
        assert second["neural"]["edges"] == 25582938
        with pytest.raises(ValueError, match="coupling interval"):
            runner.advance(.002)
    finally:
        runner.close()

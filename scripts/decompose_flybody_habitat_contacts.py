"""Read retained contact forces; no simulations and no changed pass/fail gates."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PATHS = ["validation/flybody-habitat-results.json","validation/flybody-habitat-shallow-contact-results.json"]
OUT = ROOT/"validation/flybody-habitat-contact-decomposition.json"


def main():
    if OUT.exists():
        raise FileExistsError("Preserve contact decomposition")
    files = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in PATHS}
    records = []
    for path in PATHS:
        receipt = json.loads((ROOT/path).read_text())
        probes = receipt.get("probes") or receipt["cases"]["habitat_wall_push"]["detached_contact_probes"]["probes"]
        for index,probe in enumerate(probes):
            axis,sign = index//2,(-1 if index%2==0 else 1)
            wall = probe["wall"]
            if "compiled_wall_geom_id" in probe:
                gid = probe["compiled_wall_geom_id"]
            else:
                gid = next(g["compiled_geom_id"] for g in receipt["cases"]["habitat_wall_push"]["metadata"]["habitat"]["walls"] if g["geom"]==wall)
            rows = []
            for contact in probe["sample"]["wall_contacts"]:
                if contact["wall"]!=wall or not contact["active"]:
                    continue
                orientation = 1. if contact["geom1"]==gid else -1.
                frame = np.asarray(contact["frame_world_rows"])
                force = np.asarray(contact["local_force_torque_dyne_dyne_cm"][:3])
                normal = orientation*force[0]*frame[0]
                tangent = orientation*(force[1:]@frame[1:])
                total = np.asarray(contact["force_world_dyne_on_fly"])
                rows.append({"fly_geom":contact["fly_geom"],"position_mm":contact["position_mm"],"distance_mm":contact["dist_mm"],
                    "normal_world_dyne":normal.tolist(),"tangential_world_dyne":tangent.tolist(),"total_world_dyne":total.tolist(),
                    "normal_local_force_dyne":float(force[0]),"inward_normal_axis_dyne":float(-sign*normal[axis]),
                    "inward_tangential_axis_dyne":float(-sign*tangent[axis]),"inward_total_axis_dyne":float(-sign*total[axis]),
                    "decomposition_max_error_dyne":float(np.max(abs(normal+tangent-total)))})
            records.append({"source":path,"original_overall_passed":receipt["passed"],"wall":wall,"axis":axis,
                "active_contacts":rows,"summed_inward_normal_axis_dyne":sum(c["inward_normal_axis_dyne"] for c in rows),
                "summed_inward_tangential_axis_dyne":sum(c["inward_tangential_axis_dyne"] for c in rows),
                "summed_inward_total_axis_dyne":sum(c["inward_total_axis_dyne"] for c in rows)})
    result = {"sources_sha256":files,"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "records":records,"native_steps":0,"changed_gates":False,
        "interpretation":"Positive-x deep-overlap net-axis gate and both shallow y-wall net-axis gates remain failed. All shallow probes have inward normal force. At the y-wall lower edges, a larger tangential horizontal component reverses total horizontal force. This is saved-data decomposition, not a new successful controller trial or a revised pass threshold."}
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"records":len(records),"original_gates_unchanged":True}))


if __name__=="__main__":
    main()

# Source-native proboscis geometry boundary

Installed **FlyGym 2.1.0 / MuJoCo 3.9.0** can construct an isolated rostrum and
haustellum hinge rig, but it supplies no NeuroMechFly proboscis extension
trajectory, angle limits or identified mouth opening. The smallest justified
result today is the original geometry plus infinitesimal kinematic validation.
No production body, neural decoder, ingestion rule or viewer was changed.

The [executed script](../scripts/audit_proboscis_mechanics.py),
[result receipt](../validation/proboscis-mechanics/results.json) and
[rendered geometry](../validation/proboscis-mechanics/source-geometry.png)
preserve the source hashes, actual compiled arrays and **14 passing checks**.
The packaged meshes are attributed to NeuroMechFly/FlyGym; the installed
distribution declares Apache-2.0 and its license is copied beside the derived
geometry. No extra assets or packages were downloaded.

```sh
.venv/bin/python scripts/audit_proboscis_mechanics.py
```

## What the installed source actually provides

The kinematic chain is `c_head → c_rostrum → c_haustellum`. The supplied parent
attachment translations, in model millimetres, are:

| Child | Position relative to parent (mm) | Quaternion (w,x,y,z) |
|---|---|---|
| Head, relative to thorax | (0.0287, 0, 0.000698) | (1,0,0,0) |
| Rostrum, relative to head | (0.43, 0, −0.274) | (1,0,0,0) |
| Haustellum, relative to rostrum | (−0.371, 0, −0.0196) | (1,0,0,0) |

`JointPreset.ALL_BIOLOGICAL` retains **three axes per proboscis joint**. Its
special restrictions apply to legs, so the preset's name is not evidence of a
validated six-DOF proboscis. There is no source-specific two-DOF oral preset.
The diagnostic explicitly selects one pitch hinge on each connection through
`AnatomicalJoint`/`Skeleton`, keeping head and thorax fixed. This is an API subset
chosen for inspection, not an experimentally established joint model.

Both selected pitch axes are local **(0,1,0)**. FlyGym's other axis labels use
roll=(0,0,1) and yaw=(1,0,0); do not assume a different robotics convention.
The supplied neutral pose contains only leg entries, so both added proboscis
hinges take the API's **zero-radian fallback**. Compiled `jnt_limited=False` and
`actuator_ctrllimited=False`; their stored `[0,0]` ranges are unused, not a
biological zero-motion constraint.

The generic joint defaults are stiffness=10, damping=0.5, armature=1e−6 and
spring reference=0. Generic position actuators compile with gain 1, bias
coefficient −1 and actuator-force limits [−30,30] in native units. These are
composition/MuJoCo defaults, with no proboscis physiological calibration. The
assay does not apply a dynamic control pulse or reinterpret those values as
muscle properties. Standalone `fly.compile()` disables static-body fusion on a
copy as documented by the API; the receipt retains that warning.

## Geometry, contacts and executed verification

Rostrum and haustellum use the bundled simplified mesh geoms (817/746 compiled
vertices; 2000/1998 faces). There is no separate labellar valve, aperture or pump
in this NeuroMechFly segment chain. Both oral geoms have collision masks
`contype=conaffinity=0`; contacts require explicit pairs or a declared collision
configuration. These meshes also belong to visual group 2, which the eye-view
configuration hides. Rendered surface appearance therefore does not imply oral
contact physics or visual self-occlusion in the active simulator.

Source STL vertices, scaled by the package's factor 1000 and transformed by
body frames, agree with the actual compiled mesh/world transforms to at most
**1.67×10⁻⁸ mm**. This check includes MuJoCo's internal mesh reorientation, so
body and compiled geom coordinate frames are not silently conflated.

For a reproducible fiducial, the diagnostic retains the haustellum vertex
farthest from its own hinge origin: body-local approximately
**(0.338221, 0, −0.143448) mm**, distance **0.367384 mm**. This is explicitly a
geometric point, **not an identified mouth tip or ingestion aperture**. Its
two-hinge point Jacobian agrees with an independent cross-product construction
exactly at the sampled pose and with central finite differences to
**6.84×10⁻¹¹ mm/rad** using ±1e−6 rad. Those infinitesimal perturbations are
numerical derivatives, not extension poses or safe physiological limits.

The figure shows three views of the same original zero pose plus mesh points
and joint origins. All 14 checks pass, including zero elapsed simulation time,
zero generated contacts and unchanged source files. No arbitrary angular sweep
was performed because source limits and measured extension kinematics are absent.

## Smallest next physical extension experiment

First recover measured rostrum/haustellum trajectories with their angle
conventions and identify an anatomical oral-contact landmark on the geometry.
Then use a fixed-head isolated rig to replay that measured extension/withdrawal
and test its transformed landmark against a simple external surface at measured
heights. Add explicit, reviewed collision geometry where contact is intended;
do not designate every haustellum-mesh collision as ingestion. A later bounded
actuator model needs measured dynamics and a motor-neuron/muscle crosswalk.

The separately bundled FlyBody model has oral joint ranges and extra segments,
but its geometry, frames and parameters differ; those ranges cannot be copied
into NeuroMechFly without registration and evidence. Neither adding joints nor
reaching an external surface supplies labellar opening, a cibarial pump,
pharyngeal feedback or swallowed-volume measurement. Those remain separate
boundaries described in [the feeding expansion notes](feeding-motor-expansion.md).

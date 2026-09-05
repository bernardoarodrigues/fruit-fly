"""Opt-in native environment geometry; no controller or neural operations.

Configuration uses millimeters. MuJoCo/FlyBody geometry uses centimeters.
The floor keeps its original plane collision surface; four finite-height walls
enclose a finite interior. Resource discs remain noncolliding planar regions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping

# Public MjvGeom fields in the pinned MuJoCo 3.2.7 renderer. Native model/data
# fields are never assigned by the scene callback.
SCENE_GEOM_FIELDS = ("type", "dataid", "objtype", "objid", "category", "matid",
    "texcoord", "segid", "size", "pos", "mat", "rgba", "emission", "specular",
    "shininess", "reflectance", "label", "camdist", "modelrbound", "transparent")


@dataclass(frozen=True)
class FlyBodyHabitatConfig:
    inner_size_mm: tuple[float, float] = (30., 24.)
    center_mm: tuple[float, float] = (0., 0.)
    wall_height_mm: float = 6.
    wall_thickness_mm: float = 1.

    def __post_init__(self):
        for name in ("inner_size_mm", "center_mm"):
            values = getattr(self, name)
            if (not isinstance(values, (tuple, list)) or len(values)!=2
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values)):
                raise ValueError(name+" must contain two finite numbers in millimeters")
            object.__setattr__(self, name, tuple(float(v) for v in values))
        for name in ("wall_height_mm", "wall_thickness_mm"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value<=0:
                raise ValueError(name+" must be positive and finite")
        if min(self.inner_size_mm)<=0:
            raise ValueError("Habitat inner dimensions must be positive")
        # A declared engineering clearance for the fixed native reset pose.
        if any(abs(center)+3. >= size/2 for center, size in zip(self.center_mm, self.inner_size_mm)):
            raise ValueError("Habitat must leave more than3mm clearance around the fixed source initial XY pose")

    def validate_regions(self, resources):
        for kind, region in resources.items():
            if any(abs(float(x)-center)+float(region["radius_mm"]) > size/2
                   for x, center, size in zip(region["position_mm"], self.center_mm, self.inner_size_mm)):
                raise ValueError(kind+" planar resource region must fit inside habitat inner walls")


def settings(value):
    if isinstance(value, Mapping):
        return FlyBodyHabitatConfig(**dict(value))
    if isinstance(value, FlyBodyHabitatConfig):
        return value
    raise ValueError("habitat must be null or a FlyBodyHabitatConfig mapping")


class NativeHabitat:
    """Install MJCF before reset; read compiled geometry and detached contacts."""

    def __init__(self, config, resources):
        self.config = settings(config)
        self.resources = resources
        self.config.validate_regions(resources)

    def install(self, arena, ground_geoms):
        import numpy as np
        if len(ground_geoms)!=1 or ground_geoms[0].type!="plane":
            raise ValueError("Habitat requires the pinned single plane floor")
        floor = ground_geoms[0]
        position = np.zeros(3) if floor.pos is None else np.asarray(floor.pos, dtype=float)
        quaternion = np.array([1.,0,0,0]) if floor.quat is None else np.asarray(floor.quat, dtype=float)
        if not np.array_equal(quaternion, [1.,0,0,0]):
            raise ValueError("Habitat requires a horizontal native floor")
        self.floor_z_cm = float(position[2])
        half = np.asarray(self.config.inner_size_mm)/20.
        center = np.asarray(self.config.center_mm)/10.
        thickness = self.config.wall_thickness_mm/10.
        height = self.config.wall_height_mm/10.
        old_size = np.asarray(floor.size, dtype=float)
        # Plane size controls visible extent, not the infinite collision plane.
        floor.size = (half[0]+thickness, half[1]+thickness, old_size[2])
        floor.pos = (*center, self.floor_z_cm)
        self.floor_identifier = floor.full_identifier
        self.wall_identifiers = []
        for axis, axis_name in enumerate(("x", "y")):
            for sign, side in ((-1,"neg"),(1,"pos")):
                pos = [*center, self.floor_z_cm+height/2]
                pos[axis] += sign*(half[axis]+thickness/2)
                size = [half[0], half[1], height/2]
                size[axis] = thickness/2
                # X walls include corner overlap; Y walls meet their inner face.
                if axis==0:
                    size[1] += thickness
                wall = arena.worldbody.add("geom", name=f"habitat_wall_{axis_name}_{side}", type="box",
                    pos=pos, size=size, rgba=(.5,.62,.7,.35), contype=1, conaffinity=1, condim=3,
                    friction=floor.friction, solref=floor.solref, solimp=floor.solimp, group=0)
                self.wall_identifiers.append(wall.full_identifier)
        self.site_identifiers = {}
        for kind, color in (("food",(.95,.65,.15,.9)),("water",(.15,.55,.95,.9))):
            region = self.resources[kind]
            xy = np.asarray(region["position_mm"])/10.
            # Same footprint as sensing; 2 micrometers total visual thickness.
            site = arena.worldbody.add("site", name="resource_"+kind, type="cylinder",
                pos=(*xy,self.floor_z_cm+.0001), size=(region["radius_mm"]/10.,.0001), rgba=color, group=0)
            self.site_identifiers[kind] = site.full_identifier

    def bind(self, model):
        self.wall_ids = [model.name2id(name,"geom") for name in self.wall_identifiers]
        if min(self.wall_ids)<0:
            raise ValueError("Compiled habitat walls missing")
        floor_id = model.name2id(self.floor_identifier,"geom")
        import numpy as np
        for gid in self.wall_ids:
            for field in ("geom_friction", "geom_solref", "geom_solimp"):
                if not np.array_equal(getattr(model,field)[gid],getattr(model,field)[floor_id]):
                    raise ValueError("Compiled wall contact parameters differ from source floor: "+field)
        self.metadata = {"enabled":True, **asdict(self.config), "units":"mm; native MuJoCo centimeters converted by 10",
            "floor_z_mm":self.floor_z_cm*10, "floor_collision":"unchanged infinite plane inside finite-height enclosure",
            "visible_floor_center_mm":(model.geom_pos[floor_id]*10).tolist(),
            "visible_floor_half_size_mm":(model.geom_size[floor_id,:2]*10).tolist(),
            "open_top":True, "containment_scope":"Finite-height physical walls; no root clipping, steering or guaranteed indefinite containment",
            "resource_contact":"Active tarsal floor contacts within planar center/radius; wall contacts excluded",
            "odor_boundary":"Unbounded uniform puff advection; no wall-flow or odor-boundary coupling",
            "walls":[], "resource_regions":{}}
        # Identifiers for edits to the camera's derived MjvScene only.
        self.visual_ghost_ids = {i for i in range(model.ngeom)
            if (model.id2name(i,"geom") or "").startswith("ghost/")}
        self.visual_trajectory_ids = {i for i in range(model.nsite)
            if (model.id2name(i,"site") or "").startswith("traj_")}
        self.visual_resource_ids = {}
        self.metadata["display"] = {"resource_marker_lift_mm":.05,
            "scope":"Camera MjvScene only; compiled native model/data and planar sensing unchanged",
            "reference_ghost_visible":False,"reference_trajectory_visible":False,
            "reference_filter":"Removed from MjvScene, including shadow/reflection passes"}
        for gid in self.wall_ids:
            self.metadata["walls"].append({"geom":model.id2name(gid,"geom"), "compiled_geom_id":int(gid),
                "center_mm":(model.geom_pos[gid]*10).tolist(), "half_size_mm":(model.geom_size[gid]*10).tolist(),
                "contype":int(model.geom_contype[gid]), "conaffinity":int(model.geom_conaffinity[gid]),
                "friction":model.geom_friction[gid].tolist(), "solref":model.geom_solref[gid].tolist(), "solimp":model.geom_solimp[gid].tolist()})
        for kind, name in self.site_identifiers.items():
            sid = model.name2id(name,"site")
            if sid<0:
                raise ValueError("Compiled resource site missing")
            self.visual_resource_ids[sid] = kind
            self.metadata["resource_regions"][kind] = {"site":name, "center_mm":(model.site_pos[sid]*10).tolist(),
                "radius_mm":float(model.site_size[sid,0]*10), "visual_half_thickness_mm":float(model.site_size[sid,1]*10),
                "collision_surface":self.floor_identifier, "separate_collision_geometry":False}

    def render_scene_callback(self, physics, scene):
        """Adjust disposable visualization geoms after dm-control scene update.

        Moving the rendered disc above the coplanar floor avoids depth conflict.
        The 0.05 mm lift is a display offset, not food height or collision mass.
        Reference ghosts and trajectory dots remain in native task state.
        """
        import mujoco
        import numpy as np
        removed = []
        destination = 0
        original_count = scene.ngeom
        for index in range(original_count):
            source = scene.geoms[index]
            is_site = source.objtype==mujoco.mjtObj.mjOBJ_SITE
            is_ghost = source.objtype==mujoco.mjtObj.mjOBJ_GEOM and source.objid in self.visual_ghost_ids
            is_trajectory = is_site and source.objid in self.visual_trajectory_ids
            if is_ghost or is_trajectory:
                removed.append({"original_scene_index":index,"native_object_type":int(source.objtype),
                    "native_object_id":int(source.objid),"kind":"ghost" if is_ghost else "trajectory"})
                continue
            target = scene.geoms[destination]
            if destination!=index:
                for field in SCENE_GEOM_FIELDS:
                    value = getattr(source,field)
                    if isinstance(value,np.ndarray):
                        getattr(target,field)[:] = value
                    else:
                        setattr(target,field,value)
            if is_site and source.objid in self.visual_resource_ids:
                target.pos[2] += .005  # cm: 0.05 mm, renderer only.
            if target.segid!=-1:
                target.segid = destination
            destination += 1
        scene.ngeom = destination
        self.last_render_scene_filter = {"original_count":original_count,"retained_count":destination,
            "removed":removed,"resource_marker_lift_mm":.05}

    def sample(self, model, diagnostic, root_position_cm):
        import numpy as np
        import mujoco
        contacts = []
        wall_ids = set(self.wall_ids)
        force = np.empty(6)
        for index, contact in enumerate(diagnostic.contact):
            if contact.geom1 in wall_ids:
                wall, gid, sign = int(contact.geom1), int(contact.geom2), 1.
            elif contact.geom2 in wall_ids:
                wall, gid, sign = int(contact.geom2), int(contact.geom1), -1.
            else:
                continue
            name = model.id2name(gid,"geom") or ""
            if not name.startswith("walker/"):
                continue
            mujoco.mj_contactForce(model.ptr,diagnostic,index,force)
            vector = sign*(force[:3]@contact.frame.reshape(3,3))
            contacts.append({"wall":model.id2name(wall,"geom"), "fly_geom":name,
                "geom1":int(contact.geom1), "geom2":int(contact.geom2),
                "frame_world_rows":contact.frame.reshape(3,3).tolist(),
                "local_force_torque_dyne_dyne_cm":force.tolist(),
                "dist_mm":float(contact.dist*10), "position_mm":(contact.pos*10).tolist(),
                "force_world_dyne_on_fly":vector.tolist(),
                "active":bool(contact.efc_address>=0 and contact.dist<=0)})
        xy = np.asarray(root_position_cm[:2])*10
        center = np.asarray(self.config.center_mm)
        half = np.asarray(self.config.inner_size_mm)/2
        clearance = np.r_[xy-(center-half),(center+half)-xy]
        return {"root_position_mm":xy.tolist(), "root_inside_inner_xy":bool((clearance>=0).all()),
                "root_clearance_mm_xneg_yneg_xpos_ypos":clearance.tolist(), "wall_contacts":contacts}

    def overview_pose(self):
        return [self.config.center_mm[0]/10,self.config.center_mm[1]/10,self.floor_z_cm], max(self.config.inner_size_mm)/10*1.6

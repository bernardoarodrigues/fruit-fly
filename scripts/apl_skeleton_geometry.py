"""Native SWC forest geometry for local APL anatomy, without electrical laws."""
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree


class SkeletonForest:
    def __init__(self, path, unit_um=0.008):
        raw = np.loadtxt(Path(path))
        if raw.ndim != 2 or raw.shape[1] != 7 or not np.isfinite(raw).all():
            raise ValueError('SWC must contain seven finite columns')
        if not np.array_equal(raw[:, [0, 1, 6]], np.rint(raw[:, [0, 1, 6]])):
            raise ValueError('SWC IDs, types and parents must be integers')
        raw = raw[np.argsort(raw[:, 0])]
        self.ids = raw[:, 0].astype(np.int64)
        if len(np.unique(self.ids)) != len(raw) or np.any(self.ids <= 0):
            raise ValueError('Positive unique SWC IDs required')
        if not np.isfinite(unit_um) or unit_um <= 0 or np.any(raw[:, 5] < 0):
            raise ValueError('Positive coordinate scale and nonnegative radii required')
        self.xyz = raw[:, 2:5] * unit_um
        self.radius = raw[:, 5] * unit_um
        roots = raw[:, 6] == -1
        parents = np.searchsorted(self.ids, raw[:, 6].astype(np.int64))
        valid = ~roots
        if np.any(parents[valid] >= len(raw)) or not np.array_equal(self.ids[parents[valid]], raw[valid, 6]):
            raise ValueError('Missing SWC parent')
        parents[roots] = np.flatnonzero(roots)
        if np.any(parents[valid] == np.flatnonzero(valid)):
            raise ValueError('Self-parent outside root')
        self.parent = parents
        self.roots = np.flatnonzero(roots)
        self.length = np.linalg.norm(self.xyz - self.xyz[parents], axis=1)
        self.component = np.full(len(raw), -1, dtype=np.int64)
        self.depth = np.zeros(len(raw), dtype=np.int64)
        self.root_distance = np.zeros(len(raw))
        children = [[] for _ in raw]
        for child in np.flatnonzero(valid):
            children[parents[child]].append(child)
        for ci, root in enumerate(self.roots):
            stack = [int(root)]
            self.component[root] = ci
            while stack:
                p = stack.pop()
                for c in children[p]:
                    if self.component[c] != -1:
                        raise ValueError('Cycle in SWC')
                    self.component[c] = ci
                    self.depth[c] = self.depth[p] + 1
                    self.root_distance[c] = self.root_distance[p] + self.length[c]
                    stack.append(c)
        if np.any(self.component < 0):
            raise ValueError('Cycle or unreachable component in SWC')
        levels = max(1, int(self.depth.max()).bit_length())
        self.up = np.empty((levels, len(raw)), dtype=np.int64)
        self.up[0] = parents
        for level in range(1, levels):
            self.up[level] = self.up[level-1, self.up[level-1]]
        self.centers = (self.xyz + self.xyz[parents]) / 2
        self.center_tree = cKDTree(self.centers)
        self.node_tree = cKDTree(self.xyz)

    def node_distance(self, i, j):
        if self.component[i] != self.component[j]:
            return float('inf')
        a, b = int(i), int(j)
        if self.depth[a] < self.depth[b]:
            a, b = b, a
        delta = int(self.depth[a] - self.depth[b])
        for k in range(len(self.up)):
            if delta & (1 << k):
                a = int(self.up[k, a])
        if a != b:
            for k in reversed(range(len(self.up))):
                if self.up[k, a] != self.up[k, b]:
                    a, b = int(self.up[k, a]), int(self.up[k, b])
            a = int(self.parent[a])
        return float(self.root_distance[i] + self.root_distance[j] - 2*self.root_distance[a])

    def attachment_distance(self, edge_i, fraction_i, edge_j, fraction_j):
        """Path along the forest between edge projections; gaps remain infinite."""
        if not (0 <= fraction_i <= 1 and 0 <= fraction_j <= 1):
            raise ValueError('Edge fractions must be in [0,1]')
        if self.component[edge_i] != self.component[edge_j]:
            return float('inf')
        if edge_i == edge_j:
            return float(abs(fraction_i-fraction_j)*self.length[edge_i])
        ai = [(edge_i, fraction_i*self.length[edge_i]),
              (self.parent[edge_i], (1-fraction_i)*self.length[edge_i])]
        aj = [(edge_j, fraction_j*self.length[edge_j]),
              (self.parent[edge_j], (1-fraction_j)*self.length[edge_j])]
        return min(x+y+self.node_distance(i,j) for i,x in ai for j,y in aj)

    def attach(self, points_um):
        """Exact nearest-segment search, including degenerate root segments.

        A nearest node gives an upper bound. Every potentially closer segment's
        midpoint lies within that bound plus the maximum half segment length.
        No Euclidean gap is added to the topology.
        """
        points = np.asarray(points_um, dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
            raise ValueError('Finite N-by-3 point coordinates required')
        upper = self.node_tree.query(points)[0]
        bound = self.length.max()/2
        edge = np.empty(len(points), dtype=np.int64)
        fraction = np.empty(len(points))
        residual = np.empty(len(points))
        for i, point in enumerate(points):
            candidates = np.sort(self.center_tree.query_ball_point(point, upper[i]+bound+1e-9))
            start = self.xyz[candidates]
            vector = self.xyz[self.parent[candidates]] - start
            square = np.einsum('ij,ij->i', vector, vector)
            dot = np.einsum('ij,ij->i', point-start, vector)
            t = np.clip(np.divide(dot, square, out=np.zeros_like(dot), where=square>0), 0, 1)
            dist = np.linalg.norm(point-start-t[:,None]*vector, axis=1)
            winner = int(np.argmin(dist))
            edge[i], fraction[i], residual[i] = candidates[winner], t[winner], dist[winner]
        return edge, fraction, residual

import math
import numpy as np
import pytest
from scripts.apl_skeleton_geometry import SkeletonForest


@pytest.fixture
def fork(tmp_path):
    path = tmp_path/'fork.swc'
    # Two disconnected trees, including a branch junction and unequal lengths.
    path.write_text('1 0 0 0 0 1 -1\n2 0 2 0 0 1 1\n3 0 2 3 0 1 2\n'
                    '4 0 2 -4 0 1 2\n5 0 20 20 0 1 -1\n6 0 21 20 0 1 5\n')
    return SkeletonForest(path, unit_um=1.)


def test_fork_path_lengths_and_disconnect(fork):
    assert fork.node_distance(2, 3) == 7
    assert fork.node_distance(0, 2) == 5
    assert fork.node_distance(4, 5) == 1
    assert math.isinf(fork.node_distance(0, 4))
    assert fork.node_distance(3, 3) == 0


def test_interior_projections_and_path_between_them(fork):
    points=np.array([[2,1,0],[2,-2,0],[.5,0,0],[1.5,0,0],[20,20,0],[1,1,1]])
    edges,t,residual=fork.attach(points)
    np.testing.assert_allclose(residual, [0,0,0,0,0,math.sqrt(2)], atol=1e-14)
    assert fork.attachment_distance(edges[0],t[0],edges[1],t[1]) == pytest.approx(3.)
    assert fork.attachment_distance(edges[2],t[2],edges[3],t[3]) == pytest.approx(1.)
    assert math.isinf(fork.attachment_distance(edges[0],t[0],edges[4],t[4]))
    # A nearest-node substitute would incorrectly place the first point 1 um away.
    assert fork.node_tree.query(points[0])[0] == 1


@pytest.mark.parametrize('content', [
    '1 0 0 0 0 1 2\n2 0 1 0 0 1 1\n',  # cycle without a root
    '1 0 0 0 0 1 -1\n2 0 1 0 0 1 8\n',  # absent parent
    '1 0 0 0 0 1 -1\n1 0 1 0 0 1 -1\n',  # repeated ID
])
def test_invalid_topology_is_not_repaired(tmp_path, content):
    path=tmp_path/'bad.swc'
    path.write_text(content)
    with pytest.raises(ValueError):
        SkeletonForest(path)

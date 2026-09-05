import numpy as np

from fruitfly.data import map_ids, SIGN_RULE


def test_unmapped_ids_do_not_alias_neighbouring_neurons():
    ids = np.array([5, 20, 100], dtype=np.int64)
    values = np.array([0, 5, 6, 20, 21, 100, 101])
    indices, valid = map_ids(ids, values)
    np.testing.assert_array_equal(values[valid], ids[indices[valid]])
    np.testing.assert_array_equal(valid, [False, True, False, True, False, True, False])


def test_unknown_sign_is_explicitly_neutral_not_assumed_excitatory():
    assert SIGN_RULE['unclear'] == 0
    assert SIGN_RULE['unknown'] == 0

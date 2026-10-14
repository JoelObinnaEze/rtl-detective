from backend.evaluate import regression_matrix


def test_offline_matrix_contains_all_required_width_depth_pairs() -> None:
    pairs = {(item.data_width, item.depth) for item in regression_matrix()}

    assert len(pairs) == 18
    assert {width for width, _ in pairs} == {1, 8, 16}
    assert {depth for _, depth in pairs} == {1, 2, 3, 4, 7, 8}


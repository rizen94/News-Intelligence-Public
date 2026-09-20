"""Domain-shaped protein ledger + chronicle attachment tests."""

from __future__ import annotations

from services.embedding_link_candidate_service import _collision_pair_prior


def test_collision_prior_chemistry_boosts_entity():
    linear = _collision_pair_prior(
        centroid_cos=0.5, entity_jaccard=0.8, temporal_proximity=0.9, chemistry_kind=False
    )
    chem = _collision_pair_prior(
        centroid_cos=0.5, entity_jaccard=0.8, temporal_proximity=0.9, chemistry_kind=True
    )
    assert chem > linear


def test_collision_prior_linear_weights_sum_to_one_shape():
    linear = _collision_pair_prior(
        centroid_cos=0.0, entity_jaccard=0.0, temporal_proximity=1.0, chemistry_kind=False
    )
    chem = _collision_pair_prior(
        centroid_cos=0.0, entity_jaccard=0.0, temporal_proximity=1.0, chemistry_kind=True
    )
    assert abs(linear - 0.2) < 1e-6
    assert abs(chem - 0.1) < 1e-6

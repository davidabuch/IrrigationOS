"""Canonical functional-group hierarchy for curated Plant Knowledge profiles."""

from __future__ import annotations

from ..models import ConsumerCapability, LifecycleState, PlantFunctionalGroup

_LEARNING_VISUAL_WATER = (
    ConsumerCapability.LEARNING,
    ConsumerCapability.VISUAL_IDENTIFICATION,
    ConsumerCapability.WATER_DEMAND,
)


def curated_functional_groups() -> tuple[PlantFunctionalGroup, ...]:
    """Return deterministic published functional groups without importing claims."""
    return (
        PlantFunctionalGroup(
            group_id="pk.group.california_native",
            display_name="California Native",
            description=(
                "Cross-cutting membership for plants native to California; membership alone "
                "does not imply a water requirement or import claims."
            ),
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
        ),
        PlantFunctionalGroup(
            group_id="pk.group.herbaceous",
            display_name="Herbaceous Plants",
            description="Non-woody landscape plants represented as a broad descriptive group.",
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
        ),
        PlantFunctionalGroup(
            group_id="pk.group.herbaceous.groundcover",
            display_name="Herbaceous Groundcovers",
            description="Low-growing non-woody plants commonly used for landscape coverage.",
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
            parent_group_id="pk.group.herbaceous",
        ),
        PlantFunctionalGroup(
            group_id="pk.group.herbaceous.ornamental_grass",
            display_name="Ornamental Grasses and Grasslike Plants",
            description=(
                "Grasses and grasslike plants used ornamentally rather than as mown turf."
            ),
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
            parent_group_id="pk.group.herbaceous",
        ),
        PlantFunctionalGroup(
            group_id="pk.group.mediterranean_climate",
            display_name="Mediterranean-Climate Plants",
            description=(
                "Cross-cutting membership for plants associated with Mediterranean-climate "
                "landscapes; membership does not establish regional suitability by itself."
            ),
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
        ),
        PlantFunctionalGroup(
            group_id="pk.group.succulent",
            display_name="Succulents",
            description="Plants with water-storing tissues represented as a descriptive group.",
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
        ),
        PlantFunctionalGroup(
            group_id="pk.group.turfgrass",
            display_name="Turfgrasses",
            description="Grass species or mixtures managed as mown landscape turf.",
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
        ),
        PlantFunctionalGroup(
            group_id="pk.group.woody",
            display_name="Woody Plants",
            description="Plants maintaining persistent woody stems above ground.",
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
        ),
        PlantFunctionalGroup(
            group_id="pk.group.woody.shrub",
            display_name="Woody Shrubs",
            description="Multi-stemmed or low-branching woody landscape plants.",
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
            parent_group_id="pk.group.woody",
        ),
        PlantFunctionalGroup(
            group_id="pk.group.woody.tree",
            display_name="Woody Trees",
            description="Woody plants commonly represented with a tree growth habit.",
            intended_consumer_capabilities=_LEARNING_VISUAL_WATER,
            lifecycle_state=LifecycleState.PUBLISHED,
            version=1,
            parent_group_id="pk.group.woody",
        ),
    )

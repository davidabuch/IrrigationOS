"""Aggregate validation and checksums for Plant Knowledge libraries."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .models import (
    MAX_FUNCTIONAL_GROUP_DEPTH,
    MAX_PROFILE_INHERITANCE_DEPTH,
    PLANT_KNOWLEDGE_SCHEMA_VERSION,
    ClaimConfidenceStatistics,
    ClaimResolution,
    ClaimResolutionMethod,
    EvidenceGrade,
    LifecycleState,
    PlantFunctionalGroup,
    PlantKnowledgeClaim,
    PlantKnowledgeManifest,
    PlantKnowledgeProfile,
    PlantKnowledgeSource,
    ProfileResolutionLevel,
    ReviewState,
    SerializableKnowledgeModel,
    _normalize_text,
    _usda_zone_key,
)


def _ordered_unique_map(
    name: str,
    collection: tuple[Any, ...],
    identifier_field: str,
) -> dict[str, Any]:
    if not isinstance(collection, tuple):
        raise ValueError(f"{name} must be an immutable tuple")
    identifiers = tuple(getattr(item, identifier_field) for item in collection)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{name} must have unique identifiers")
    if identifiers != tuple(sorted(identifiers)):
        raise ValueError(f"{name} must use deterministic canonical-ID ordering")
    return dict(zip(identifiers, collection, strict=True))


def _checksum_payload(
    *,
    manifest: PlantKnowledgeManifest,
    sources: tuple[PlantKnowledgeSource, ...],
    claims: tuple[PlantKnowledgeClaim, ...],
    claim_resolutions: tuple[ClaimResolution, ...],
    functional_groups: tuple[PlantFunctionalGroup, ...],
    profiles: tuple[PlantKnowledgeProfile, ...],
) -> dict[str, object]:
    manifest_data = manifest.to_dict()
    manifest_data.pop("validation_checksum")
    return {
        "manifest": manifest_data,
        "sources": [item.to_dict() for item in sorted(sources, key=lambda item: item.source_id)],
        "claims": [item.to_dict() for item in sorted(claims, key=lambda item: item.claim_id)],
        "claim_resolutions": [
            item.to_dict()
            for item in sorted(claim_resolutions, key=lambda item: item.resolution_id)
        ],
        "functional_groups": [
            item.to_dict() for item in sorted(functional_groups, key=lambda item: item.group_id)
        ],
        "profiles": [item.to_dict() for item in sorted(profiles, key=lambda item: item.profile_id)],
    }


def calculate_library_checksum(
    *,
    manifest: PlantKnowledgeManifest,
    sources: tuple[PlantKnowledgeSource, ...],
    claims: tuple[PlantKnowledgeClaim, ...],
    claim_resolutions: tuple[ClaimResolution, ...],
    functional_groups: tuple[PlantFunctionalGroup, ...],
    profiles: tuple[PlantKnowledgeProfile, ...],
) -> str:
    """Calculate the stable SHA-256 checksum for complete library content."""
    payload = _checksum_payload(
        manifest=manifest,
        sources=sources,
        claims=claims,
        claim_resolutions=claim_resolutions,
        functional_groups=functional_groups,
        profiles=profiles,
    )
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class PlantKnowledgeLibrary(SerializableKnowledgeModel):
    """Complete immutable, checksummed Plant Knowledge library aggregate."""

    manifest: PlantKnowledgeManifest
    sources: tuple[PlantKnowledgeSource, ...]
    claims: tuple[PlantKnowledgeClaim, ...]
    claim_resolutions: tuple[ClaimResolution, ...]
    functional_groups: tuple[PlantFunctionalGroup, ...]
    profiles: tuple[PlantKnowledgeProfile, ...]

    def __post_init__(self) -> None:
        source_by_id = _ordered_unique_map("sources", self.sources, "source_id")
        claim_by_id = _ordered_unique_map("claims", self.claims, "claim_id")
        resolution_by_id = _ordered_unique_map(
            "claim_resolutions", self.claim_resolutions, "resolution_id"
        )
        group_by_id = _ordered_unique_map("functional_groups", self.functional_groups, "group_id")
        profile_by_id = _ordered_unique_map("profiles", self.profiles, "profile_id")

        self._validate_claim_references(source_by_id, claim_by_id)
        self._validate_claim_resolutions(claim_by_id, resolution_by_id)
        self._validate_group_graph(group_by_id)
        self._validate_profile_graph(profile_by_id, group_by_id, claim_by_id)
        self._validate_supersession_graphs(claim_by_id, profile_by_id)
        self._validate_published_profiles(source_by_id, claim_by_id, profile_by_id)
        self._validate_ambiguity(profile_by_id)
        self._validate_manifest()
        expected_checksum = calculate_library_checksum(
            manifest=self.manifest,
            sources=self.sources,
            claims=self.claims,
            claim_resolutions=self.claim_resolutions,
            functional_groups=self.functional_groups,
            profiles=self.profiles,
        )
        if self.manifest.validation_checksum != expected_checksum:
            raise ValueError("manifest validation checksum does not match library content")

    def _validate_claim_references(
        self,
        source_by_id: dict[str, PlantKnowledgeSource],
        claim_by_id: dict[str, PlantKnowledgeClaim],
    ) -> None:
        for claim in self.claims:
            missing = set(claim.source_ids) - set(source_by_id)
            if missing:
                raise ValueError(f"claim references unknown sources: {sorted(missing)}")
            if claim.superseded_claim_id is not None:
                successor = claim_by_id.get(claim.superseded_claim_id)
                if successor is None:
                    raise ValueError("claim references an unknown superseding claim")
                if successor.field_path != claim.field_path:
                    raise ValueError("superseding claims must use the same field path")

    def _validate_claim_resolutions(
        self,
        claim_by_id: dict[str, PlantKnowledgeClaim],
        resolution_by_id: dict[str, ClaimResolution],
    ) -> None:
        del resolution_by_id
        seen_competing_sets: set[tuple[str, tuple[str, ...]]] = set()
        for resolution in self.claim_resolutions:
            missing = set(resolution.competing_claim_ids) - set(claim_by_id)
            if missing:
                raise ValueError(f"claim resolution references unknown claims: {sorted(missing)}")
            field_paths = {
                claim_by_id[claim_id].field_path for claim_id in resolution.competing_claim_ids
            }
            if field_paths != {resolution.field_path}:
                raise ValueError("competing claims must share the resolution field path")
            key = (resolution.field_path, resolution.competing_claim_ids)
            if key in seen_competing_sets:
                raise ValueError("duplicate claim resolution for the same competing claims")
            seen_competing_sets.add(key)

    def _validate_group_graph(self, group_by_id: dict[str, PlantFunctionalGroup]) -> None:
        parents = {group.group_id: group.parent_group_id for group in self.functional_groups}
        for group_id, parent_id in parents.items():
            if parent_id is not None and parent_id not in group_by_id:
                raise ValueError(f"functional group {group_id} has an unknown parent")
        _validate_acyclic_bounded_graph(
            "functional-group hierarchy",
            parents,
            MAX_FUNCTIONAL_GROUP_DEPTH,
        )

    def _validate_profile_graph(
        self,
        profile_by_id: dict[str, PlantKnowledgeProfile],
        group_by_id: dict[str, PlantFunctionalGroup],
        claim_by_id: dict[str, PlantKnowledgeClaim],
    ) -> None:
        parents = {profile.profile_id: profile.parent_profile_id for profile in self.profiles}
        for profile in self.profiles:
            if profile.parent_profile_id is not None:
                parent = profile_by_id.get(profile.parent_profile_id)
                if parent is None:
                    raise ValueError(f"profile {profile.profile_id} has an unknown parent")
                if parent.resolution_level is ProfileResolutionLevel.CULTIVAR:
                    raise ValueError("cultivar profiles cannot serve as parent profiles")
            missing_groups = set(profile.functional_group_ids) - set(group_by_id)
            if missing_groups:
                raise ValueError(
                    f"profile references unknown functional groups: {sorted(missing_groups)}"
                )
            missing_claims = set(profile.claim_ids) - set(claim_by_id)
            if missing_claims:
                raise ValueError(f"profile references unknown claims: {sorted(missing_claims)}")
        _validate_acyclic_bounded_graph(
            "profile inheritance",
            parents,
            MAX_PROFILE_INHERITANCE_DEPTH,
        )

    def _validate_supersession_graphs(
        self,
        claim_by_id: dict[str, PlantKnowledgeClaim],
        profile_by_id: dict[str, PlantKnowledgeProfile],
    ) -> None:
        claim_successors = {claim.claim_id: claim.superseded_claim_id for claim in self.claims}
        _validate_acyclic_bounded_graph(
            "claim supersession",
            claim_successors,
            len(claim_by_id) or 1,
        )
        profile_successors = {
            profile.profile_id: profile.superseded_profile_id for profile in self.profiles
        }
        for profile_id, successor_id in profile_successors.items():
            if successor_id is not None and successor_id not in profile_by_id:
                raise ValueError(f"profile {profile_id} has an unknown superseding profile")
        _validate_acyclic_bounded_graph(
            "profile supersession",
            profile_successors,
            len(profile_by_id) or 1,
        )

    def _validate_published_profiles(
        self,
        source_by_id: dict[str, PlantKnowledgeSource],
        claim_by_id: dict[str, PlantKnowledgeClaim],
        profile_by_id: dict[str, PlantKnowledgeProfile],
    ) -> None:
        for profile in self.profiles:
            if profile.lifecycle_state is not LifecycleState.PUBLISHED:
                continue
            chain = _profile_chain(profile.profile_id, profile_by_id)
            effective_claims, conflicts = _effective_claims(chain, claim_by_id)
            if conflicts:
                unresolved_fields = {
                    field_path
                    for field_path, claim_ids in conflicts.items()
                    if not self._has_resolution(field_path, claim_ids)
                }
                if unresolved_fields:
                    raise ValueError(
                        "published profile has unresolved claim conflicts: "
                        f"{sorted(unresolved_fields)}"
                    )
            identity_claims = [
                claim
                for claim in effective_claims.values()
                if claim.field_path
                in {"identity.scientific_name", "identity.preferred_common_name"}
                and claim.review_state is ReviewState.APPROVED
                and claim.source_ids
            ]
            if not identity_claims:
                raise ValueError(
                    "published profiles require approved source-backed identity knowledge"
                )
            relevant_approved = [
                claim
                for claim in effective_claims.values()
                if claim.review_state is ReviewState.APPROVED
                and set(claim.intended_consumer_capabilities)
                & set(profile.intended_consumer_capabilities)
            ]
            if not relevant_approved:
                raise ValueError(
                    "published profiles require an approved claim relevant to a consumer"
                )
            supporting = {claim.claim_id: claim for claim in (*identity_claims, *relevant_approved)}
            for claim in supporting.values():
                if not claim.source_ids:
                    raise ValueError("published supporting claims must be source-backed")
                for source_id in claim.source_ids:
                    source = source_by_id[source_id]
                    if source.review_state not in {ReviewState.REVIEWED, ReviewState.APPROVED}:
                        raise ValueError("published claims require reviewed or approved sources")
            if all(
                claim.evidence_grade is EvidenceGrade.PROVISIONAL for claim in supporting.values()
            ):
                raise ValueError(
                    "published profiles cannot rely exclusively on provisional evidence"
                )

    def _has_resolution(self, field_path: str, claim_ids: tuple[str, ...]) -> bool:
        claim_set = set(claim_ids)
        return any(
            resolution.field_path == field_path
            and claim_set == set(resolution.competing_claim_ids)
            and resolution.resolution_method is not ClaimResolutionMethod.UNRESOLVED
            for resolution in self.claim_resolutions
        )

    def _validate_ambiguity(self, profile_by_id: dict[str, PlantKnowledgeProfile]) -> None:
        del profile_by_id
        scientific_keys: set[tuple[str, str, str]] = set()
        fallback_keys: set[tuple[str, str, str]] = set()
        for profile in self.profiles:
            if profile.lifecycle_state is not LifecycleState.PUBLISHED:
                continue
            region = json.dumps(
                profile.regional_applicability.to_dict(),
                separators=(",", ":"),
                sort_keys=True,
            )
            if profile.resolution_level in {
                ProfileResolutionLevel.CULTIVAR,
                ProfileResolutionLevel.SPECIES,
                ProfileResolutionLevel.GENUS,
            }:
                key = (
                    _normalize_text(profile.scientific_name or ""),
                    _normalize_text(profile.cultivar or ""),
                    region,
                )
                if key in scientific_keys:
                    raise ValueError(
                        "ambiguous duplicate published scientific-name and cultivar identity"
                    )
                scientific_keys.add(key)
            if profile.resolution_level in {
                ProfileResolutionLevel.CATEGORY_FALLBACK,
                ProfileResolutionLevel.UNKNOWN_FALLBACK,
            }:
                key = (
                    profile.resolution_level.value,
                    profile.broad_category.value,
                    region,
                )
                if key in fallback_keys:
                    raise ValueError("ambiguous duplicate published fallback identity")
                fallback_keys.add(key)

    def _validate_manifest(self) -> None:
        if self.manifest.schema_version != PLANT_KNOWLEDGE_SCHEMA_VERSION:
            raise ValueError("manifest schema_version is not supported")
        if any(profile.schema_version != self.manifest.schema_version for profile in self.profiles):
            raise ValueError("profile schema versions must match the manifest")
        expected_counts = {
            "profile_count": len(self.profiles),
            "category_count": sum(
                profile.resolution_level is ProfileResolutionLevel.CATEGORY_FALLBACK
                for profile in self.profiles
            ),
            "functional_group_count": len(self.functional_groups),
            "genus_count": sum(
                profile.resolution_level is ProfileResolutionLevel.GENUS
                for profile in self.profiles
            ),
            "species_count": sum(
                profile.resolution_level is ProfileResolutionLevel.SPECIES
                for profile in self.profiles
            ),
            "cultivar_count": sum(
                profile.resolution_level is ProfileResolutionLevel.CULTIVAR
                for profile in self.profiles
            ),
            "source_count": len(self.sources),
            "claim_count": len(self.claims),
            "claim_resolution_count": len(self.claim_resolutions),
            "published_profile_count": sum(
                profile.lifecycle_state is LifecycleState.PUBLISHED for profile in self.profiles
            ),
        }
        for name, expected in expected_counts.items():
            if getattr(self.manifest, name) != expected:
                raise ValueError(f"manifest {name} does not match aggregate content")
        expected_statistics = _confidence_statistics(self.claims)
        if self.manifest.confidence_statistics != expected_statistics:
            raise ValueError("manifest confidence statistics do not match claims")
        regions = tuple(
            sorted(
                {
                    region
                    for applicability in (
                        *(profile.regional_applicability for profile in self.profiles),
                        *(claim.regional_applicability for claim in self.claims),
                    )
                    for region in applicability.climate_zone_ids
                },
                key=str.casefold,
            )
        )
        if self.manifest.supported_climate_regions != regions:
            raise ValueError("manifest supported climate regions do not match content")
        zones = [
            zone
            for applicability in (
                *(profile.regional_applicability for profile in self.profiles),
                *(claim.regional_applicability for claim in self.claims),
            )
            for zone in (
                applicability.usda_zone_minimum,
                applicability.usda_zone_maximum,
            )
            if zone is not None
        ]
        expected_min: str | None
        expected_max: str | None
        if zones:
            expected_min = min(zones, key=_usda_zone_key)
            expected_max = max(zones, key=_usda_zone_key)
        else:
            expected_min = expected_max = None
        if (
            self.manifest.usda_zone_minimum,
            self.manifest.usda_zone_maximum,
        ) != (expected_min, expected_max):
            raise ValueError("manifest USDA summary does not match content")

    def get_profile(self, profile_id: str) -> PlantKnowledgeProfile:
        """Return a profile by stable canonical identity."""
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(f"unknown plant-knowledge profile: {profile_id}")

    def get_claim(self, claim_id: str) -> PlantKnowledgeClaim:
        """Return a claim by stable canonical identity."""
        for claim in self.claims:
            if claim.claim_id == claim_id:
                return claim
        raise KeyError(f"unknown plant-knowledge claim: {claim_id}")


def _confidence_statistics(
    claims: tuple[PlantKnowledgeClaim, ...],
) -> ClaimConfidenceStatistics:
    if not claims:
        return ClaimConfidenceStatistics(0, None, None, None)
    confidences = tuple(claim.confidence for claim in claims)
    return ClaimConfidenceStatistics(
        claim_count=len(confidences),
        minimum=min(confidences),
        maximum=max(confidences),
        mean=round(sum(confidences) / len(confidences), 6),
    )


def _validate_acyclic_bounded_graph(
    name: str,
    parents: dict[str, str | None],
    maximum_depth: int,
) -> None:
    for node_id in parents:
        seen: set[str] = set()
        current: str | None = node_id
        depth = 0
        while current is not None:
            if current in seen:
                raise ValueError(f"{name} must be acyclic")
            seen.add(current)
            depth += 1
            if depth > maximum_depth:
                raise ValueError(f"{name} exceeds maximum depth {maximum_depth}")
            current = parents.get(current)


def _profile_chain(
    profile_id: str,
    profile_by_id: dict[str, PlantKnowledgeProfile],
) -> tuple[PlantKnowledgeProfile, ...]:
    chain: list[PlantKnowledgeProfile] = []
    current: PlantKnowledgeProfile | None = profile_by_id[profile_id]
    while current is not None:
        chain.append(current)
        current = (
            profile_by_id[current.parent_profile_id]
            if current.parent_profile_id is not None
            else None
        )
    return tuple(reversed(chain))


def _effective_claims(
    chain: tuple[PlantKnowledgeProfile, ...],
    claim_by_id: dict[str, PlantKnowledgeClaim],
) -> tuple[dict[str, PlantKnowledgeClaim], dict[str, tuple[str, ...]]]:
    effective: dict[str, PlantKnowledgeClaim] = {}
    conflicts: dict[str, tuple[str, ...]] = {}
    for profile in chain:
        layer: dict[str, list[PlantKnowledgeClaim]] = {}
        for claim_id in profile.claim_ids:
            claim = claim_by_id[claim_id]
            layer.setdefault(claim.field_path, []).append(claim)
        for field_path, claims in layer.items():
            ordered = tuple(sorted(claims, key=lambda item: item.claim_id))
            if len(ordered) > 1 or any(claim.unresolved_conflict for claim in ordered):
                conflicts[field_path] = tuple(claim.claim_id for claim in ordered)
            effective[field_path] = max(
                ordered,
                key=lambda item: (
                    item.review_state is ReviewState.APPROVED,
                    item.confidence,
                    item.claim_version,
                    item.claim_id,
                ),
            )
    return effective, conflicts

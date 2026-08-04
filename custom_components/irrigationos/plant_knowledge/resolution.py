"""Deterministic exact-match resolution for Plant Knowledge profiles."""

from __future__ import annotations

from dataclasses import replace

from .library import PlantKnowledgeLibrary
from .models import (
    PLANT_KNOWLEDGE_RESOLUTION_ALGORITHM_VERSION,
    ClaimResolution,
    ClaimTraceDisposition,
    CoastalApplicability,
    EffectivePlantKnowledgeClaim,
    InheritedClaimTrace,
    InlandApplicability,
    LifecycleState,
    PlantKnowledgeClaim,
    PlantKnowledgeExplanation,
    PlantKnowledgeProfile,
    PlantKnowledgeResolution,
    PlantKnowledgeResolutionCandidate,
    PlantKnowledgeResolutionRequest,
    ProfileResolutionLevel,
    ResolutionReasonCode,
    _normalize_text,
    _usda_zone_key,
)

_IDENTITY_SCORES = {
    ProfileResolutionLevel.CULTIVAR: 90,
    ProfileResolutionLevel.SPECIES: 80,
    ProfileResolutionLevel.GENUS: 70,
    ProfileResolutionLevel.FUNCTIONAL_GROUP: 60,
    ProfileResolutionLevel.CATEGORY_FALLBACK: 50,
    ProfileResolutionLevel.UNKNOWN_FALLBACK: 10,
}
_PRECEDENCE = tuple(_IDENTITY_SCORES)
_REASON_BY_LEVEL = {
    ProfileResolutionLevel.CULTIVAR: ResolutionReasonCode.EXACT_CULTIVAR_MATCH,
    ProfileResolutionLevel.SPECIES: ResolutionReasonCode.EXACT_SPECIES_MATCH,
    ProfileResolutionLevel.GENUS: ResolutionReasonCode.EXACT_GENUS_MATCH,
    ProfileResolutionLevel.FUNCTIONAL_GROUP: ResolutionReasonCode.FUNCTIONAL_GROUP_MATCH,
    ProfileResolutionLevel.CATEGORY_FALLBACK: ResolutionReasonCode.CATEGORY_FALLBACK,
    ProfileResolutionLevel.UNKNOWN_FALLBACK: ResolutionReasonCode.UNKNOWN_FALLBACK,
}
_REVIEW_STATE_RANK = {
    "approved": 5,
    "reviewed": 4,
    "unreviewed": 3,
    "deprecated": 2,
    "rejected": 1,
}


def _normalized_optional(value: str | None) -> str | None:
    return _normalize_text(value) if value is not None else None


def _profile_names(profile: PlantKnowledgeProfile) -> tuple[str, ...]:
    names = (
        profile.preferred_common_name,
        *(profile.aliases),
        *((profile.scientific_name,) if profile.scientific_name is not None else ()),
    )
    return tuple(_normalize_text(value) for value in names)


def _identity_match(
    profile: PlantKnowledgeProfile,
    request: PlantKnowledgeResolutionRequest,
) -> tuple[int, tuple[str, ...], str]:
    names = _profile_names(profile)
    scientific = _normalized_optional(request.scientific_name)
    common = _normalized_optional(request.common_name)
    cultivar = _normalized_optional(request.cultivar)
    matched_aliases = tuple(
        sorted(
            alias
            for alias in profile.aliases
            if _normalize_text(alias) in {value for value in (scientific, common) if value}
        )
    )
    level = profile.resolution_level
    matched = False
    if level is ProfileResolutionLevel.CULTIVAR:
        matched = cultivar is not None and cultivar == _normalized_optional(profile.cultivar)
        if matched and scientific is not None:
            matched = scientific in names
    elif level in {ProfileResolutionLevel.SPECIES, ProfileResolutionLevel.GENUS}:
        matched = any(value is not None and value in names for value in (scientific, common))
    elif level is ProfileResolutionLevel.FUNCTIONAL_GROUP:
        matched = bool(set(profile.functional_group_ids) & set(request.functional_group_hints))
    elif level is ProfileResolutionLevel.CATEGORY_FALLBACK:
        matched = (
            request.broad_category is not None and request.broad_category is profile.broad_category
        )
    elif level is ProfileResolutionLevel.UNKNOWN_FALLBACK:
        matched = True
    if not matched:
        return 0, matched_aliases, "no_identity_match"
    return _IDENTITY_SCORES[level], matched_aliases, _REASON_BY_LEVEL[level].value


def _regional_score(
    profile: PlantKnowledgeProfile,
    request: PlantKnowledgeResolutionRequest,
) -> tuple[int, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    applicability = profile.regional_applicability
    matched: list[str] = []
    unavailable: list[str] = []
    mismatched: list[str] = []

    def compare_membership(attribute: str, requested: str | None, allowed: tuple[str, ...]) -> None:
        if requested is None:
            return
        if not allowed:
            unavailable.append(attribute)
        elif _normalize_text(requested) in {_normalize_text(value) for value in allowed}:
            matched.append(attribute)
        else:
            mismatched.append(attribute)

    compare_membership("country", request.country, applicability.countries)
    compare_membership(
        "state_or_province",
        request.state_or_province,
        applicability.states_or_provinces,
    )
    compare_membership("wucols_region", request.wucols_region, applicability.wucols_regions)
    if request.climate_zone_ids:
        if not applicability.climate_zone_ids:
            unavailable.append("climate_zone_ids")
        elif {_normalize_text(value) for value in request.climate_zone_ids} & {
            _normalize_text(value) for value in applicability.climate_zone_ids
        }:
            matched.append("climate_zone_ids")
        else:
            mismatched.append("climate_zone_ids")
    if request.usda_hardiness_zone is not None:
        if applicability.usda_zone_minimum is None:
            unavailable.append("usda_hardiness_zone")
        elif (
            _usda_zone_key(applicability.usda_zone_minimum)
            <= _usda_zone_key(request.usda_hardiness_zone)
            <= _usda_zone_key(applicability.usda_zone_maximum or "1a")
        ):
            matched.append("usda_hardiness_zone")
        else:
            mismatched.append("usda_hardiness_zone")

    def compare_context(
        attribute: str,
        requested: bool | None,
        applies: bool | None,
    ) -> None:
        if requested is None:
            return
        if applies is None:
            unavailable.append(attribute)
        elif requested is applies:
            matched.append(attribute)
        else:
            mismatched.append(attribute)

    coastal = {
        CoastalApplicability.APPLIES: True,
        CoastalApplicability.DOES_NOT_APPLY: False,
        CoastalApplicability.UNSPECIFIED: None,
    }[applicability.coastal]
    inland = {
        InlandApplicability.APPLIES: True,
        InlandApplicability.DOES_NOT_APPLY: False,
        InlandApplicability.UNSPECIFIED: None,
    }[applicability.inland]
    compare_context("coastal", request.coastal, coastal)
    compare_context("inland", request.inland, inland)

    if not matched and not unavailable and not mismatched:
        unavailable.append("regional_context")
    if mismatched:
        score = -10
    elif matched and not unavailable:
        score = 10
    elif matched:
        score = 5
    else:
        score = 0
    return (
        score,
        tuple(sorted(matched)),
        tuple(sorted(unavailable)),
        tuple(sorted(mismatched)),
    )


def _candidate(
    profile: PlantKnowledgeProfile,
    request: PlantKnowledgeResolutionRequest,
    *,
    override: bool,
) -> PlantKnowledgeResolutionCandidate:
    lifecycle_eligible = profile.lifecycle_state not in {
        LifecycleState.DEPRECATED,
        LifecycleState.SUPERSEDED,
    }
    aliases: tuple[str, ...]
    if override:
        identity_score, aliases, reason = 100, (), "user_confirmed_override"
    else:
        identity_score, aliases, reason = _identity_match(profile, request)
    regional_score, matched, unavailable, mismatched = _regional_score(profile, request)
    eligible = lifecycle_eligible and identity_score > 0
    if not lifecycle_eligible:
        reason = "lifecycle_excluded"
    return PlantKnowledgeResolutionCandidate(
        profile_id=profile.profile_id,
        resolution_level=profile.resolution_level,
        identity_score=identity_score,
        regional_score=regional_score,
        total_score=identity_score + regional_score,
        matched_aliases=aliases,
        matched_regional_attributes=matched,
        unavailable_regional_attributes=unavailable,
        mismatched_regional_attributes=mismatched,
        eligible=eligible,
        reason_code=reason,
    )


def _inheritance_chain(
    selected: PlantKnowledgeProfile,
    profiles: dict[str, PlantKnowledgeProfile],
) -> tuple[PlantKnowledgeProfile, ...]:
    chain: list[PlantKnowledgeProfile] = []
    current: PlantKnowledgeProfile | None = selected
    while current is not None:
        chain.append(current)
        current = (
            profiles[current.parent_profile_id] if current.parent_profile_id is not None else None
        )
    return tuple(reversed(chain))


def _selected_competing_claim(
    library: PlantKnowledgeLibrary,
    claims: tuple[PlantKnowledgeClaim, ...],
) -> tuple[PlantKnowledgeClaim, ClaimResolution | None, bool]:
    claim_ids = {claim.claim_id for claim in claims}
    for resolution in library.claim_resolutions:
        if claim_ids == set(resolution.competing_claim_ids):
            selected = (
                library.get_claim(resolution.selected_claim_id)
                if resolution.selected_claim_id is not None
                else _ranked_claim(claims)
            )
            return selected, resolution, bool(resolution.unresolved_issues)
    return (
        _ranked_claim(claims),
        None,
        len(claims) > 1 or any(claim.unresolved_conflict for claim in claims),
    )


def _ranked_claim(claims: tuple[PlantKnowledgeClaim, ...]) -> PlantKnowledgeClaim:
    """Choose a deterministic provenance anchor when no claim is explicitly selected."""
    selected = max(
        claims,
        key=lambda claim: (
            _REVIEW_STATE_RANK[claim.review_state.value],
            claim.confidence,
            claim.claim_version,
            claim.claim_id,
        ),
    )
    return selected


def _resolve_effective_claims(
    library: PlantKnowledgeLibrary,
    chain: tuple[PlantKnowledgeProfile, ...],
) -> tuple[
    tuple[EffectivePlantKnowledgeClaim, ...],
    tuple[InheritedClaimTrace, ...],
    bool,
]:
    effective: dict[
        str,
        tuple[PlantKnowledgeClaim, str, ClaimResolution | None, bool],
    ] = {}
    traces: list[InheritedClaimTrace] = []
    unresolved = False
    selected_profile_id = chain[-1].profile_id
    for profile in chain:
        claims_by_field: dict[str, list[PlantKnowledgeClaim]] = {}
        for claim_id in profile.claim_ids:
            claim = library.get_claim(claim_id)
            claims_by_field.setdefault(claim.field_path, []).append(claim)
        for field_path in sorted(claims_by_field):
            layer_claims = tuple(
                sorted(claims_by_field[field_path], key=lambda claim: claim.claim_id)
            )
            selected, resolution, layer_unresolved = _selected_competing_claim(
                library, layer_claims
            )
            unresolved = unresolved or layer_unresolved
            previous = effective.get(field_path)
            if previous is not None:
                previous_claim, _, _, _ = previous
                for index, trace in enumerate(traces):
                    if (
                        trace.claim_id == previous_claim.claim_id
                        and trace.disposition is ClaimTraceDisposition.EFFECTIVE
                    ):
                        traces[index] = replace(
                            trace,
                            disposition=ClaimTraceDisposition.OVERRIDDEN,
                            overridden_by_claim_id=selected.claim_id,
                        )
            for claim in layer_claims:
                if claim.claim_id == selected.claim_id:
                    continue
                traces.append(
                    InheritedClaimTrace(
                        claim_id=claim.claim_id,
                        field_path=field_path,
                        originating_profile_id=profile.profile_id,
                        disposition=ClaimTraceDisposition.CONFLICT_RETAINED,
                    )
                )
            effective[field_path] = (
                selected,
                profile.profile_id,
                resolution,
                layer_unresolved,
            )
            traces.append(
                InheritedClaimTrace(
                    claim_id=selected.claim_id,
                    field_path=field_path,
                    originating_profile_id=profile.profile_id,
                    disposition=ClaimTraceDisposition.EFFECTIVE,
                )
            )
    effective_models = tuple(
        EffectivePlantKnowledgeClaim(
            claim_id=claim.claim_id,
            field_path=field_path,
            value=(
                resolution.resolved_range
                if resolution is not None and resolution.resolved_range is not None
                else claim.value
            ),
            unit=(
                resolution.resolved_range.unit
                if resolution is not None and resolution.resolved_range is not None
                else claim.unit
            ),
            originating_profile_id=origin,
            source_ids=claim.source_ids,
            review_state=claim.review_state,
            evidence_grade=claim.evidence_grade,
            confidence=claim.confidence,
            regional_applicability=claim.regional_applicability,
            intended_consumer_capabilities=claim.intended_consumer_capabilities,
            claim_version=claim.claim_version,
            inherited=origin != selected_profile_id,
            conflict_unresolved=layer_unresolved,
            claim_resolution_id=(resolution.resolution_id if resolution is not None else None),
            resolved_range=(resolution.resolved_range if resolution is not None else None),
            claim_resolution=resolution,
        )
        for field_path, (claim, origin, resolution, layer_unresolved) in sorted(
            effective.items()
        )
    )
    return effective_models, tuple(traces), unresolved


def resolve_plant_knowledge(
    library: PlantKnowledgeLibrary,
    request: PlantKnowledgeResolutionRequest,
) -> PlantKnowledgeResolution:
    """Resolve a profile using versioned exact-match precedence and regional scoring."""
    profiles = {profile.profile_id: profile for profile in library.profiles}
    override_id = request.user_confirmed_profile_id
    if override_id is not None and override_id not in profiles:
        raise ValueError("user-confirmed profile override does not exist")
    candidates = tuple(
        _candidate(profile, request, override=profile.profile_id == override_id)
        for profile in library.profiles
    )

    selected_candidate: PlantKnowledgeResolutionCandidate | None = None
    fallback_chain: list[ProfileResolutionLevel] = []
    if override_id is not None:
        override_candidate = next(
            candidate for candidate in candidates if candidate.profile_id == override_id
        )
        if not override_candidate.eligible:
            raise ValueError("user-confirmed profile override is deprecated or superseded")
        selected_candidate = override_candidate
        reason_code = ResolutionReasonCode.USER_CONFIRMED_OVERRIDE
    else:
        reason_code = ResolutionReasonCode.NO_ELIGIBLE_PROFILE
        for level in _PRECEDENCE:
            fallback_chain.append(level)
            at_level = [
                candidate
                for candidate in candidates
                if candidate.eligible and candidate.resolution_level is level
            ]
            if at_level:
                selected_candidate = max(
                    at_level,
                    key=lambda candidate: (candidate.regional_score, -len(candidate.profile_id)),
                )
                best_score = max(candidate.regional_score for candidate in at_level)
                tied = sorted(
                    candidate.profile_id
                    for candidate in at_level
                    if candidate.regional_score == best_score
                )
                selected_candidate = next(
                    candidate for candidate in at_level if candidate.profile_id == tied[0]
                )
                reason_code = _REASON_BY_LEVEL[level]
                break

    if selected_candidate is None:
        explanation = PlantKnowledgeExplanation(
            reason_code=ResolutionReasonCode.NO_ELIGIBLE_PROFILE,
            summary="No eligible canonical plant-knowledge profile matched the request.",
            algorithm_version=PLANT_KNOWLEDGE_RESOLUTION_ALGORITHM_VERSION,
            candidate_profile_ids=tuple(candidate.profile_id for candidate in candidates),
            evidence_source_ids=(),
            matched_regional_attributes=(),
            unavailable_regional_attributes=("profile_match",),
            mismatched_regional_attributes=(),
            inherited_claim_ids=(),
            overridden_claim_ids=(),
        )
        return PlantKnowledgeResolution(
            request_id=request.request_id,
            selected_profile_id=None,
            selected_resolution_level=None,
            candidates=candidates,
            matched_aliases=(),
            fallback_chain=tuple(fallback_chain),
            profile_inheritance_chain=(),
            effective_claims=(),
            claim_traces=(),
            resolution_confidence=0,
            unresolved_ambiguity=False,
            suggested_verification_action="Confirm a canonical plant identity or category.",
            reason_code=ResolutionReasonCode.NO_ELIGIBLE_PROFILE,
            explanation=explanation,
            algorithm_version=PLANT_KNOWLEDGE_RESOLUTION_ALGORITHM_VERSION,
        )

    selected_profile = profiles[selected_candidate.profile_id]
    chain = _inheritance_chain(selected_profile, profiles)
    effective_claims, traces, claim_ambiguity = _resolve_effective_claims(library, chain)
    same_level_best = tuple(
        candidate
        for candidate in candidates
        if candidate.eligible
        and candidate.resolution_level is selected_candidate.resolution_level
        and candidate.regional_score == selected_candidate.regional_score
    )
    identity_ambiguity = len(same_level_best) > 1 and override_id is None
    ambiguity = identity_ambiguity or claim_ambiguity
    if identity_ambiguity:
        reason_code = ResolutionReasonCode.AMBIGUOUS_MATCH
    confidence = max(0.0, min(1.0, selected_candidate.total_score / 110))
    inherited_ids = tuple(sorted(claim.claim_id for claim in effective_claims if claim.inherited))
    overridden_ids = tuple(
        sorted(
            trace.claim_id
            for trace in traces
            if trace.disposition is ClaimTraceDisposition.OVERRIDDEN
        )
    )
    resolution_by_id = {
        resolution.resolution_id: resolution for resolution in library.claim_resolutions
    }
    evidence_claim_ids = {
        claim_id
        for effective in effective_claims
        for claim_id in (
            resolution_by_id[effective.claim_resolution_id].competing_claim_ids
            if effective.claim_resolution_id is not None
            else (effective.claim_id,)
        )
    }
    source_ids = tuple(
        sorted(
            {
                source_id
                for claim_id in evidence_claim_ids
                for source_id in library.get_claim(claim_id).source_ids
            }
        )
    )
    suggestion: str | None = None
    if ambiguity:
        suggestion = "Confirm the exact canonical profile or review conflicting claims."
    elif selected_candidate.unavailable_regional_attributes:
        suggestion = "Confirm regional context to strengthen profile applicability."
    summary = (
        f"Selected {selected_profile.profile_id} at "
        f"{selected_profile.resolution_level.value} precedence using exact matching."
    )
    explanation = PlantKnowledgeExplanation(
        reason_code=reason_code,
        summary=summary,
        algorithm_version=PLANT_KNOWLEDGE_RESOLUTION_ALGORITHM_VERSION,
        candidate_profile_ids=tuple(candidate.profile_id for candidate in candidates),
        evidence_source_ids=source_ids,
        matched_regional_attributes=selected_candidate.matched_regional_attributes,
        unavailable_regional_attributes=selected_candidate.unavailable_regional_attributes,
        mismatched_regional_attributes=selected_candidate.mismatched_regional_attributes,
        inherited_claim_ids=inherited_ids,
        overridden_claim_ids=overridden_ids,
    )
    return PlantKnowledgeResolution(
        request_id=request.request_id,
        selected_profile_id=selected_profile.profile_id,
        selected_resolution_level=selected_profile.resolution_level,
        candidates=candidates,
        matched_aliases=selected_candidate.matched_aliases,
        fallback_chain=tuple(fallback_chain),
        profile_inheritance_chain=tuple(profile.profile_id for profile in chain),
        effective_claims=effective_claims,
        claim_traces=traces,
        resolution_confidence=round(confidence, 6),
        unresolved_ambiguity=ambiguity,
        suggested_verification_action=suggestion,
        reason_code=reason_code,
        explanation=explanation,
        algorithm_version=PLANT_KNOWLEDGE_RESOLUTION_ALGORITHM_VERSION,
    )

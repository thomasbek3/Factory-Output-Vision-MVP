import json

from app.services.label_quality import (
    CandidateLabel,
    LabelQualityConfig,
    ReviewContext,
    ReviewDecision,
    ReviewOutcome,
    build_review_card,
    polygon_to_box,
    review_label,
)


def test_accepts_good_active_panel_box():
    label = CandidateLabel(
        label_id="frame-001-panel-1",
        frame_id="frame-001",
        image_width=1000,
        image_height=800,
        class_name="active_panel",
        box=(200, 160, 520, 420),
        confidence=0.94,
        source_type="box",
    )

    outcome = review_label(label)

    assert outcome.decision == ReviewDecision.ACCEPT
    assert outcome.reason_codes == ["active_panel_box_plausible"]
    assert outcome.fixed_label is None


def test_accepts_panel_class_when_allowed_by_default():
    label = CandidateLabel(
        label_id="frame-001-panel-1",
        frame_id="frame-001",
        image_width=1000,
        image_height=800,
        class_name="panel",
        box=(200, 160, 520, 420),
        confidence=0.94,
        source_type="box",
    )

    outcome = review_label(label)

    assert outcome.decision == ReviewDecision.ACCEPT
    assert outcome.reason_codes == ["active_panel_box_plausible"]


def test_rejects_panel_class_when_allowed_classes_are_overridden():
    label = CandidateLabel(
        label_id="frame-001-panel-1",
        frame_id="frame-001",
        image_width=1000,
        image_height=800,
        class_name="panel",
        box=(200, 160, 520, 420),
        confidence=0.94,
        source_type="box",
    )

    outcome = review_label(
        label,
        config=LabelQualityConfig(allowed_class_names=("active_panel",)),
    )

    assert outcome.decision == ReviewDecision.REJECT
    assert "wrong_class" in outcome.reason_codes


def test_rejects_non_active_panel_class_before_training():
    label = CandidateLabel(
        label_id="frame-001-person-1",
        frame_id="frame-001",
        image_width=1000,
        image_height=800,
        class_name="person",
        box=(200, 160, 520, 420),
        confidence=0.99,
        source_type="box",
    )

    outcome = review_label(label)

    assert outcome.decision == ReviewDecision.REJECT
    assert "wrong_class" in outcome.reason_codes


def test_rejects_static_stack_negative_even_when_geometry_is_plausible():
    label = CandidateLabel(
        label_id="frame-001-stack-1",
        frame_id="frame-001",
        image_width=1000,
        image_height=800,
        class_name="active_panel",
        box=(80, 120, 500, 500),
        confidence=0.91,
        source_type="box",
        metadata={"static_stack": True},
    )

    outcome = review_label(label)

    assert outcome.decision == ReviewDecision.REJECT
    assert "static_stack_negative" in outcome.reason_codes


def test_fixes_polygon_to_clipped_box():
    label = CandidateLabel(
        label_id="frame-002-panel-1",
        frame_id="frame-002",
        image_width=640,
        image_height=480,
        class_name="active_panel",
        polygon=[(-8, 10), (100, 6), (120, 90), (12, 96)],
        confidence=0.88,
        source_type="polygon",
    )

    outcome = review_label(label)

    assert polygon_to_box(label.polygon) == (-8, 6, 120, 96)
    assert outcome.decision == ReviewDecision.FIX
    assert outcome.fixed_label is not None
    assert outcome.fixed_label.box == (0, 6, 120, 96)
    assert outcome.fixed_label.polygon == [(0, 10), (100, 6), (120, 90), (12, 96)]
    assert "polygon_box_clipped" in outcome.reason_codes


def test_rejects_degenerate_polygon_before_training():
    label = CandidateLabel(
        label_id="frame-002-panel-2",
        frame_id="frame-002",
        image_width=640,
        image_height=480,
        class_name="active_panel",
        polygon=[(10, 10), (20, 20), (30, 30)],
        confidence=0.88,
        source_type="polygon",
    )

    outcome = review_label(label)

    assert outcome.decision == ReviewDecision.REJECT
    assert "polygon_degenerate" in outcome.reason_codes


def test_rejects_polygon_with_fewer_than_three_points_before_training():
    label = CandidateLabel(
        label_id="frame-002-panel-3",
        frame_id="frame-002",
        image_width=640,
        image_height=480,
        class_name="active_panel",
        polygon=[(10, 10), (120, 90)],
        confidence=0.88,
        source_type="polygon",
    )

    outcome = review_label(label)

    assert outcome.decision == ReviewDecision.REJECT
    assert "polygon_too_few_points" in outcome.reason_codes


def test_flags_polygon_box_disagreement_when_both_are_present():
    label = CandidateLabel(
        label_id="frame-002-panel-4",
        frame_id="frame-002",
        image_width=640,
        image_height=480,
        class_name="active_panel",
        box=(300, 300, 420, 420),
        polygon=[(10, 10), (120, 10), (120, 90), (10, 90)],
        confidence=0.88,
        source_type="polygon",
    )

    outcome = review_label(label)

    assert outcome.decision == ReviewDecision.UNCERTAIN
    assert "polygon_box_disagreement" in outcome.reason_codes


def test_temporal_jump_returns_uncertain_review():
    label = CandidateLabel(
        label_id="frame-011-panel-1",
        frame_id="frame-011",
        image_width=1000,
        image_height=800,
        class_name="active_panel",
        box=(720, 510, 920, 690),
        confidence=0.86,
        source_type="box",
    )
    context = ReviewContext(
        previous_label=CandidateLabel(
            label_id="frame-010-panel-1",
            frame_id="frame-010",
            image_width=1000,
            image_height=800,
            class_name="active_panel",
            box=(200, 180, 400, 360),
            confidence=0.92,
            source_type="box",
        )
    )

    outcome = review_label(label, context=context)

    assert outcome.decision == ReviewDecision.UNCERTAIN
    assert "temporal_jump" in outcome.reason_codes


def test_review_card_includes_manifest_contract_for_ai_reviewer():
    label = CandidateLabel(
        label_id="frame-001-panel-1",
        frame_id="frame-001",
        image_width=1000,
        image_height=800,
        class_name="active_panel",
        box=(200, 160, 520, 420),
        confidence=0.94,
        source_type="box",
        metadata={"worker_id": "ann-7"},
    )
    outcome = ReviewOutcome(
        label_id=label.label_id,
        decision=ReviewDecision.ACCEPT,
        reason_codes=["active_panel_box_plausible"],
        score=0.96,
    )

    card = build_review_card(label, outcome)

    assert card["label_id"] == "frame-001-panel-1"
    assert card["ai_reviewer_contract"]["allowed_decisions"] == [
        "ACCEPT",
        "FIX",
        "REJECT",
        "UNCERTAIN",
    ]
    assert "active_panel" in card["prompt"]
    assert card["candidate"]["box_xyxy"] == [200, 160, 520, 420]


def test_flags_too_loose_tiny_out_of_bounds_and_overlap_signals():
    label = CandidateLabel(
        label_id="frame-003-panel-1",
        frame_id="frame-003",
        image_width=1000,
        image_height=800,
        class_name="active_panel",
        box=(-20, 10, 980, 790),
        confidence=0.62,
        source_type="box",
        metadata={"object_box": (300, 250, 340, 290)},
    )
    context = ReviewContext(
        worker_boxes=[(0, 0, 990, 790)],
        ignore_regions=[(0, 0, 1000, 800)],
    )

    outcome = review_label(
        label,
        context=context,
        config=LabelQualityConfig(min_confidence=0.80),
    )

    assert outcome.decision == ReviewDecision.REJECT
    assert set(
        [
            "box_out_of_bounds",
            "box_too_loose",
            "box_too_tiny",
            "low_confidence",
            "worker_overlap",
            "ignore_region_overlap",
        ]
    ).issubset(outcome.reason_codes)


def test_worker_overlap_returns_uncertain_instead_of_accept():
    label = CandidateLabel(
        label_id="frame-004-panel-1",
        frame_id="frame-004",
        image_width=1000,
        image_height=800,
        class_name="active_panel",
        box=(200, 160, 520, 420),
        confidence=0.94,
        source_type="box",
    )
    context = ReviewContext(worker_boxes=[(210, 170, 510, 410)])

    outcome = review_label(label, context=context)

    assert outcome.decision == ReviewDecision.UNCERTAIN
    assert "worker_overlap" in outcome.reason_codes

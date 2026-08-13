from observability_hub.domains.quality import score


def test_calculate_score_neutral_when_never_profiled_and_no_freshness_data():
    result = score.calculate_score(profiling_result=None, sla_status=None, description=None)

    assert result.breakdown.completeness == 50.0
    assert result.breakdown.freshness == 50.0
    assert result.breakdown.duplicates == 50.0
    assert result.breakdown.documentation == 0.0
    assert result.has_profiling_data is False
    # 50*0.4 + 50*0.3 + 50*0.2 + 0*0.1 = 45
    assert result.score == 45


def test_calculate_score_perfect_table():
    profiling_result = score.LastProfilingResult(overall_density=100.0, estimated_duplicate_pct=0.0)

    result = score.calculate_score(
        profiling_result=profiling_result, sla_status="ok", description="Tabela documentada"
    )

    assert result.breakdown == score.ScoreBreakdown(
        completeness=100.0, freshness=100.0, duplicates=100.0, documentation=100.0
    )
    assert result.has_profiling_data is True
    assert result.score == 100


def test_calculate_score_worst_table():
    profiling_result = score.LastProfilingResult(overall_density=0.0, estimated_duplicate_pct=50.0)

    result = score.calculate_score(
        profiling_result=profiling_result, sla_status="stale", description=None
    )

    assert result.breakdown == score.ScoreBreakdown(
        completeness=0.0, freshness=0.0, duplicates=40.0, documentation=0.0
    )
    assert result.score == 8  # 0*.4 + 0*.3 + 40*.2 + 0*.1 = 8


def test_freshness_score_matches_sla_status_table():
    cases = {
        "ok": 100.0,
        "warning_12_24": 80.0,
        "warning_24_48": 60.0,
        "warning_48_7d": 40.0,
        "warning_7d_1m": 20.0,
        "stale": 0.0,
    }
    for status, expected in cases.items():
        result = score.calculate_score(profiling_result=None, sla_status=status, description=None)
        assert result.breakdown.freshness == expected


def test_duplicates_score_buckets():
    def duplicates_score(pct: float) -> float:
        profiling_result = score.LastProfilingResult(
            overall_density=100.0, estimated_duplicate_pct=pct
        )
        return score.calculate_score(profiling_result, None, None).breakdown.duplicates

    assert duplicates_score(0) == 100.0
    assert duplicates_score(1) == 80.0
    assert duplicates_score(5) == 80.0
    assert duplicates_score(5.1) == 60.0
    assert duplicates_score(10) == 60.0
    assert duplicates_score(10.1) == 40.0
    assert duplicates_score(50) == 40.0


def test_documentation_score_binary():
    with_desc = score.calculate_score(None, None, "algo")
    without_desc = score.calculate_score(None, None, "")
    none_desc = score.calculate_score(None, None, None)

    assert with_desc.breakdown.documentation == 100.0
    assert without_desc.breakdown.documentation == 0.0
    assert none_desc.breakdown.documentation == 0.0


def test_score_is_rounded_to_int():
    profiling_result = score.LastProfilingResult(overall_density=73.0, estimated_duplicate_pct=3.0)
    result = score.calculate_score(profiling_result, "warning_24_48", None)
    # 73*.4 + 60*.3 + 80*.2 + 0*.1 = 29.2 + 18 + 16 + 0 = 63.2 -> 63
    assert result.score == 63

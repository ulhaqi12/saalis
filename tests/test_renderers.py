import json

from saalis.models import Explanation, PolicyDecision, Verdict, VerdictStatus


def make_explanation(**kwargs) -> Explanation:
    defaults = dict(
        summary="Agent A won the arbitration",
        rationale="A provided the most evidence-backed response",
        dissents=["Proposal p2 (agent a2)", "Proposal p3 (agent a3)"],
        score_breakdown={"p1": 0.85, "p2": 0.60, "p3": 0.45},
    )
    return Explanation(**{**defaults, **kwargs})


def make_verdict(**kwargs) -> Verdict:
    defaults = dict(
        decision_id="d1",
        winner_proposal_id="p1",
        strategy_name="WeightedVote",
        explanation=make_explanation(),
        policy_result=PolicyDecision(allowed=True),
        status=VerdictStatus.resolved,
    )
    return Verdict(**{**defaults, **kwargs})


# ── Explanation.text() ─────────────────────────────────────────────────────

def test_text_includes_summary():
    e = make_explanation()
    assert "Agent A won" in e.text()


def test_text_includes_rationale():
    e = make_explanation()
    assert "evidence-backed" in e.text()


def test_text_includes_dissents():
    e = make_explanation()
    assert "p2" in e.text()
    assert "p3" in e.text()


def test_text_no_dissents():
    e = make_explanation(dissents=[])
    assert "Dissenting" not in e.text()


def test_text_no_rationale():
    e = make_explanation(rationale="")
    output = e.text()
    assert "Agent A won" in output
    assert output.count("  ") == 0  # no double spaces from empty join


# ── Explanation.markdown() ─────────────────────────────────────────────────

def test_markdown_has_summary_heading():
    e = make_explanation()
    md = e.markdown()
    assert "## Decision Summary" in md
    assert "Agent A won" in md


def test_markdown_strategy_and_status():
    e = make_explanation()
    md = e.markdown(strategy_name="LLMJudge", status="resolved")
    assert "**Strategy:** LLMJudge" in md
    assert "**Status:** resolved" in md


def test_markdown_score_breakdown_table():
    e = make_explanation()
    md = e.markdown()
    assert "### Score Breakdown" in md
    assert "| p1 | 0.850 |" in md
    assert "| p2 | 0.600 |" in md


def test_markdown_scores_sorted_descending():
    e = make_explanation()
    md = e.markdown()
    p1_pos = md.index("| p1 |")
    p2_pos = md.index("| p2 |")
    assert p1_pos < p2_pos  # highest score first


def test_markdown_dissents_section():
    e = make_explanation()
    md = e.markdown()
    assert "### Dissenting Proposals" in md
    assert "- Proposal p2" in md


def test_markdown_no_score_breakdown_skips_table():
    e = make_explanation(score_breakdown={})
    md = e.markdown()
    assert "Score Breakdown" not in md


def test_markdown_no_dissents_skips_section():
    e = make_explanation(dissents=[])
    md = e.markdown()
    assert "Dissenting" not in md


# ── Verdict.render() ──────────────────────────────────────────────────────

def test_render_text_default():
    v = make_verdict()
    out = v.render()
    assert "Agent A won" in out


def test_render_markdown():
    v = make_verdict()
    out = v.render("markdown")
    assert "## Decision Summary" in out
    assert "**Strategy:** WeightedVote" in out
    assert "**Status:** resolved" in out


def test_render_json():
    v = make_verdict()
    out = v.render("json")
    parsed = json.loads(out)
    assert parsed["winner_proposal_id"] == "p1"
    assert parsed["strategy_name"] == "WeightedVote"


def test_render_unknown_format_falls_back_to_text():
    v = make_verdict()
    assert "Agent A won" in v.render("html")

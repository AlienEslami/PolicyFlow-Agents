from pathlib import Path

from policyflow.evaluation import evaluate, load_cases
from policyflow.graph import PolicyFlowService


def test_adversarial_and_bilingual_evaluation_suite(
    service: PolicyFlowService, project_root: Path
) -> None:
    cases = load_cases(project_root / "data" / "synthetic" / "evaluation_cases.json")
    report = evaluate(service, cases)

    assert report.case_count == 6
    assert report.status_accuracy == 1.0
    assert report.safety_pass_rate == 1.0
    assert report.citation_coverage == 1.0

from backend.models.generation import CitedSource
from backend.models.planner import ProcedurePlan, ProcedureStep, WorkflowStatus


def test_workflow_status_enum_values() -> None:
    assert WorkflowStatus.READY_TO_START.value == "ready_to_start"
    assert WorkflowStatus.NEEDS_MORE_INFORMATION.value == "needs_more_information"
    assert WorkflowStatus.BLOCKED.value == "blocked"
    assert WorkflowStatus.IN_PROGRESS.value == "in_progress"
    assert WorkflowStatus.COMPLETED.value == "completed"


def test_procedure_step_model_preserves_fields() -> None:
    source = CitedSource(source="driving.pdf", page=1, region="zh")
    step = ProcedureStep(
        step_number=1,
        title="Confirm residence date",
        description="Confirm when Swiss residence started.",
        responsible_party="User",
        required_documents=["Residence proof"],
        estimated_time="Not specified in retrieved sources.",
        source_reference=source,
    )

    assert step.step_number == 1
    assert step.source_reference == source


def test_procedure_plan_model_preserves_workflow_data() -> None:
    plan = ProcedurePlan(
        title="Driving licence exchange",
        summary="Exchange workflow.",
        status=WorkflowStatus.READY_TO_START,
        steps=[],
        required_documents=["Foreign driving licence"],
        estimated_timelines=["Not specified in retrieved sources."],
        potential_blockers=[],
        next_recommended_action="Confirm the residence start date.",
        source_references=[CitedSource(source="driving.pdf", page=1, region="zh")],
        missing_information=[],
    )

    assert plan.status is WorkflowStatus.READY_TO_START
    assert plan.required_documents == ["Foreign driving licence"]

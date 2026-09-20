"""Reusable, declarative lab activities. No uploaded code or expressions execute."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from .contracts import Strict


class Block(Strict):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)


class Reading(Block):
    type: Literal["reading"] = "reading"
    body: str = Field(min_length=1, max_length=30000)


class Prediction(Block):
    type: Literal["prediction"] = "prediction"
    prompt: str = Field(min_length=1, max_length=12000)


class WorkedExample(Block):
    type: Literal["worked_example"] = "worked_example"
    body: str = Field(min_length=1, max_length=30000)


class Reflection(Block):
    type: Literal["reflection"] = "reflection"
    prompt: str = Field(min_length=1, max_length=12000)


class Parameter(Strict):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    label: str = Field(min_length=1, max_length=300)
    min: float = Field(ge=-1e12, le=1e12, allow_inf_nan=False)
    max: float = Field(ge=-1e12, le=1e12, allow_inf_nan=False)
    initial: float = Field(ge=-1e12, le=1e12, allow_inf_nan=False)
    step: float = Field(default=1, gt=0, le=1e12, allow_inf_nan=False)
    coefficient: float = Field(default=1, ge=-1e12, le=1e12, allow_inf_nan=False)

    @model_validator(mode="after")
    def bounds(self):
        if self.min >= self.max or not self.min <= self.initial <= self.max:
            raise ValueError("Parameter needs min < max and an initial value inside its bounds")
        return self


class ParameterExperiment(Block):
    type: Literal["parameter_experiment"] = "parameter_experiment"
    description: str = Field(default="", max_length=12000)
    inputs: list[Parameter] = Field(min_length=1, max_length=20)
    offset: float = Field(default=0, ge=-1e12, le=1e12, allow_inf_nan=False)
    output_label: str = Field(default="Result", min_length=1, max_length=300)
    unit: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def unique_inputs(self):
        if len({p.key for p in self.inputs}) != len(self.inputs):
            raise ValueError("Experiment parameter keys must be unique")
        return self


class Assessment(Block):
    type: Literal["assessment"] = "assessment"
    mode: Literal["practice", "transfer"] = "practice"
    count: int = Field(default=3, ge=1, le=40)


class Coursework(Block):
    type: Literal["coursework"] = "coursework"
    assignment_id: str = Field(min_length=1, max_length=200)


ActivityBlock = Annotated[
    Reading | Prediction | WorkedExample | Reflection | ParameterExperiment | Assessment | Coursework,
    Field(discriminator="type"),
]


def activity_types():
    """One contract for discovery, authoring and event validation."""
    definitions = [
        (Reading, "Reading", "Grounded explanatory text.", {"body": "Explain the idea using your reviewed sources."}),
        (Prediction, "Prediction", "Save a prediction before checking a result.", {"prompt": "What do you expect, and why?"}),
        (WorkedExample, "Worked example", "Show an explained solution as preparation.", {"body": "Walk through a concrete example."}),
        (ParameterExperiment, "Parameter experiment", "A bounded weighted sum: offset + sum(coefficient × input).", {
            "description": "Change an input and compare the result with your prediction.",
            "inputs": [{"key": "x", "label": "Input", "min": 0, "max": 10, "initial": 2, "step": 1, "coefficient": 3}],
        }),
        (Reflection, "Reflection", "Save reasoning without automatically grading it.", {"prompt": "What changed your explanation?"}),
        (Assessment, "Practice assessment", "Use the gym's existing questions, timing and assessment.", {}),
        (Coursework, "Coursework", "Open an existing assignment and its versioned rubric.", {"assignment_id": "REPLACE_WITH_ASSIGNMENT_ID"}),
    ]
    result = []
    for model, title, description, fields in definitions:
        type_name = model.model_fields["type"].default
        template = model(id=type_name + "-1", title=title, **fields).model_dump(mode="json")
        result.append({"type": type_name, "title": title, "description": description,
                       "schema": model.model_json_schema(), "template": template})
    return {"version": "1.0", "types": result,
            "schema": TypeAdapter(ActivityBlock).json_schema(),
            "execution": "Declarative activities only. No arbitrary code or expressions execute."}

"""Versioned lab blocks; custom visualization code runs only in a browser sandbox."""

import json
import re
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, JsonValue, TypeAdapter, model_validator

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
    count: int = Field(default=3, ge=1, le=30)


class Coursework(Block):
    type: Literal["coursework"] = "coursework"
    assignment_id: str = Field(min_length=1, max_length=200)


class Media(Block):
    type: Literal["media"] = "media"
    kind: Literal["video", "audio"] = "video"
    provider: Literal["native", "youtube", "vimeo"] = "native"
    url: HttpUrl
    description: str = Field(default="", max_length=12000)
    transcript: str = Field(default="", max_length=30000)
    captions_url: HttpUrl | None = None
    captions_language: str = Field(default="en", pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    start_seconds: int = Field(default=0, ge=0, le=86400)
    end_seconds: int | None = Field(default=None, ge=1, le=86400)

    @model_validator(mode="after")
    def media_contract(self):
        for url in (self.url, self.captions_url):
            if url and (url.scheme != "https" or url.username or url.password):
                raise ValueError("Media and captions need HTTPS URLs without embedded credentials")
        if self.end_seconds is not None and self.end_seconds <= self.start_seconds:
            raise ValueError("Media end must follow its start")
        if self.provider != "native":
            if self.kind != "video" or self.captions_url:
                raise ValueError("Hosted video uses the provider's captions; audio needs a native URL")
            if self.url.query or self.url.fragment or self.url.port not in (None, 443):
                raise ValueError("Use an embed URL without query parameters; set playback parameters on the block")
            if self.provider == "youtube" and not (
                self.url.host == "www.youtube-nocookie.com"
                and re.fullmatch(r"/embed/[A-Za-z0-9_-]{11}", self.url.path)
            ):
                raise ValueError("Use https://www.youtube-nocookie.com/embed/VIDEO_ID")
            if self.provider == "vimeo" and not (
                self.url.host == "player.vimeo.com" and re.fullmatch(r"/video/[0-9]+", self.url.path)
            ):
                raise ValueError("Use https://player.vimeo.com/video/VIDEO_ID")
            if self.provider == "vimeo" and self.end_seconds is not None:
                raise ValueError("Vimeo embeds support a start time only; use native media for an end time")
        return self


class VisualizationParameter(Strict):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    label: str = Field(min_length=1, max_length=300)
    min: float = Field(ge=-1e12, le=1e12, allow_inf_nan=False)
    max: float = Field(ge=-1e12, le=1e12, allow_inf_nan=False)
    initial: float = Field(ge=-1e12, le=1e12, allow_inf_nan=False)
    step: float = Field(default=1, gt=0, le=1e12, allow_inf_nan=False)

    @model_validator(mode="after")
    def bounds(self):
        if self.min >= self.max or not self.min <= self.initial <= self.max:
            raise ValueError("Parameter needs min < max and an initial value inside its bounds")
        return self


class Visualization(Block):
    type: Literal["visualization"] = "visualization"
    description: str = Field(default="", max_length=12000)
    html: str = Field(min_length=1, max_length=100000)
    css: str = Field(default="", max_length=30000)
    javascript: str = Field(default="", max_length=100000)
    data: dict[str, JsonValue] = Field(default_factory=dict)
    parameters: list[VisualizationParameter] = Field(default_factory=list, max_length=20)
    height: int = Field(default=420, ge=180, le=1200)
    fallback: str = Field(min_length=1, max_length=12000)

    @model_validator(mode="after")
    def bounded_config(self):
        if len({p.key for p in self.parameters}) != len(self.parameters):
            raise ValueError("Visualization parameter keys must be unique")
        if len(json.dumps(self.data, allow_nan=False)) > 100000:
            raise ValueError("Visualization data must be at most 100000 characters")
        return self


class Discussion(Block):
    type: Literal["discussion"] = "discussion"
    prompt: str = Field(min_length=1, max_length=6000)
    objectives: list[str] = Field(default_factory=list, max_length=12)
    style: Literal["socratic", "explain", "debate"] = "socratic"
    max_turns: int = Field(default=8, ge=1, le=24)
    response_words: int = Field(default=180, ge=50, le=500)

    @model_validator(mode="after")
    def bounded_objectives(self):
        if any(not value.strip() or len(value) > 500 for value in self.objectives):
            raise ValueError("Discussion objectives must contain 1 to 500 characters")
        return self


ActivityBlock = Annotated[
    Reading | Prediction | WorkedExample | Reflection | ParameterExperiment | Assessment | Coursework
    | Media | Visualization | Discussion,
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
        (Media, "Video or audio", "Load a video or podcast on request, with a transcript and optional clip bounds.", {
            "url": "https://example.org/lesson.mp4", "transcript": "Replace with an accurate transcript.",
        }),
        (Visualization, "Interactive visualization", "Self-contained HTML/CSS/JavaScript with data and bounded controls in an isolated browser frame.", {
            "html": "<canvas id='plot' width='640' height='280'></canvas>",
            "javascript": "const c = document.querySelector('#plot').getContext('2d'); c.strokeStyle = '#386db1'; c.beginPath(); for(let x=0;x<640;x++){ const y=140-90*Math.sin(x/640*2*Math.PI*gym.parameters.frequency); x ? c.lineTo(x,y) : c.moveTo(x,y); } c.stroke();",
            "parameters": [{"key": "frequency", "label": "Frequency", "min": 1, "max": 5, "initial": 2, "step": 0.1}],
            "fallback": "Increasing frequency fits more wave cycles into the same horizontal interval.",
        }),
        (Discussion, "Discuss with a tutor", "Grounded conversation through the configured tutor role; assistance, never a grade.", {
            "prompt": "Explain your prediction. Which assumption could change it?",
        }),
    ]
    result = []
    for model, title, description, fields in definitions:
        type_name = model.model_fields["type"].default
        template = model(id=type_name + "-1", title=title, **fields).model_dump(mode="json")
        result.append({"type": type_name, "title": title, "description": description,
                       "schema": model.model_json_schema(), "template": template})
    return {"version": "2.0", "types": result,
            "schema": TypeAdapter(ActivityBlock).json_schema(),
            "execution": "Custom visualization code runs only in an isolated browser frame; never on the server. Discussions use the configured tutor role only on learner request."}

# 12. From impressive claim to evidence you can inspect

When a company or AI agent says it understands causality, what would count as evidence?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Separate a company claim, a paper's measured result, and an independent replication.

Translate action-following metrics into a bounded scientific conclusion.

Design an audit that records assumptions, interventions, comparisons, and uncertainty.

# Intuition

A causal discovery library, an agentic interface, and a company research essay serve different roles. causal-learn implements methods; CausalLearn offers an online interface; Aether's writing presents a research and product perspective. A polished interface can make a procedure easier to run, but it cannot establish the scientific assumptions for your dataset. Your task as a reader is to connect each claim to an actual method, measurement, comparison, and stated scope.

Consider a world model that predicts future video given an action. Better action following means its predictions respond more appropriately to the tested action inputs according to the evaluation. That is potentially useful evidence. It does not automatically establish that the model recovered the real-world causal graph, can answer every counterfactual, or will safely control a physical robot. Changing an action token in a simulator or video predictor is an evaluation intervention on that model, whose relation to real-world interventions needs its own evidence.

The CD-LAM preprint offers a concrete case. It reports improvements for action-conditioned world-model video prediction, and a company article summarizes efficiency gains. Inspect the training and evaluation protocol before attributing gains solely to causal reasoning: the paper's debiasing procedure uses foreground masks and coarse action labels that the baseline does not use in the described setup. This raises a testable question about auxiliary supervision and training budgets. A good critique proposes a fair comparison; it neither accepts the headline uncritically nor dismisses the research because it is a preprint.

# Make the headline testable

Rewrite 'causal world models need ten times less post-training' as a bounded claim: 'For the specified model backbones, datasets, auxiliary inputs, training-budget definition, baseline, and action-following metrics, the authors report the stated efficiency improvement.' Then propose a matched-supervision ablation: give a comparison method the same masks and action labels, match or sweep training compute, and test on held-out actions and environments. Report where performance improves, where it does not, and whether independent evaluation reproduces it.

# Try it

Choose one statement from the linked Aether article. Fill an evidence card with exact claim in your own words, evaluated system, action/intervention, measured outcome, comparison baseline, assumptions, and a missing test. Compare your card with the original preprint.

# Remember

An agent can automate an analysis; the data and assumptions still determine its scientific meaning.

Ask what intervention was tested and what outcome was actually measured.

A useful review states the strongest supported conclusion and the next experiment that could change it.

# Common mistake

Treating company ambition, a preprint benchmark, and independently replicated real-world capability as the same level of evidence.

# Research bridge

It provides a current AI research example where foundational distinctions—intervention, confounding, comparison, and scope—help interpret a frontier result.

The preprint reports improved action-following and training efficiency for its evaluated video world-model settings.

# Assumptions

The chosen action-following metrics validly capture the intended behavior in these tests.

A causal interpretation of gains needs an appropriate comparison and a justified relationship between the training intervention and measured outcome.

# Limits

This is a July 2026 research preprint; broad causal understanding and physical-robot safety are not established by these benchmarks.

The debiasing setup uses foreground masks and coarse action labels not used by the described baseline, motivating matched-supervision comparisons.

Reported gains are conditional on model backbones, data, training budgets, and evaluation protocol; the company headline should retain that scope.

# Reading task

Read the abstract, experimental setup, baseline definitions, ablations, and limitations. Then compare the company headline with the paper's specific tasks and training resources.

Write a 200-word evidence audit ending with one falsifiable follow-up test and a concrete result that would lower your confidence.

# Reflection

Write your current confidence in one causal AI claim, name the evidence behind it, and state an observation that would change your mind.

# Referenced readings (external originals)

Causality and the Next AI Paradigm (2026). Industry essay; evaluate its cited research separately from the company's broader claims.. https://aetherlabs.ai/articles/causality-and-the-next-ai-paradigm

CD-LAM: Causal Debiasing for Embodied World Models (2026). arXiv preprint, submitted July 10, 2026; benchmark evidence does not establish general causal understanding or deployed robot safety.. https://arxiv.org/abs/2607.09185

CD-LAM: Causal Debiasing Gives World Models Stronger Action Control with 10x Less Post-training (2026). Company interpretation of a preprint; not a peer-reviewed or independent replication.. https://aetherlabs.ai/articles/cd-lam-causal-debiasing-for-embodied-world-models

CausalLearn online platform (None). Interface not independently evaluated; treat outputs as hypotheses requiring assumption and evidence checks.. https://causallearn.com

py-why/causal-learn (None). Official living repository; source consulted September 2026.. https://github.com/py-why/causal-learn

Causal Inference: What If (2020). Verified public book resource; not represented as one of the user's unlocated local books.. https://miguelhernan.org/whatifbook
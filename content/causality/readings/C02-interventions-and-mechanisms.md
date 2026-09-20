# 2. A tiny world you can intervene on

What does it mean to change a cause while leaving a system's other mechanisms intact?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Read a simple structural causal model as a recipe for generating data.

Distinguish observing X=x from doing X=x.

Explain a counterfactual using the same underlying individual circumstances.

# Intuition

A structural causal model, or SCM, is a set of small recipes. One recipe says how much a person studies, another says how their score is produced. Each recipe uses its direct causes plus background factors we have not explicitly modeled. A diagram draws an arrow from an input to the recipe it enters. This is a proposed explanation of how the world works, not a picture automatically certified by the data.

An ideal intervention replaces one recipe. If study time normally depends on motivation, do(study=2) replaces that equation with 'study exactly two hours'. It breaks the usual influence of motivation on assigned study time. The score recipe still uses motivation and study. By contrast, observing study=2 selects people who naturally studied two hours; it does not erase the reasons they did so.

A counterfactual asks about an alternative outcome for the same unit: what would this learner have scored if their study time had been two hours? In a fully specified SCM, we use observed evidence to reason about that learner's background factors, replace the intervention equation, then compute the alternative outcome with those same background factors. Population intervention effects can sometimes be identified even when such individual counterfactuals cannot.

# Watching study time versus assigning it

In a toy world, motivation M is 0 or 1, study hours H=M, and score Y=50+10H+20M. The naturally observed H=1 group has score 80; the H=0 group has score 50. That observed gap is 30 points. Increasing H by one through an intervention raises Y by 10 points at either motivation level. For a learner with M=1, do(H=0) gives Y=70. These answers follow from the stated toy recipes; real data do not automatically reveal them.

# Try it

Use H=M and Y=50+10H+20M. Calculate the observed score gap between H=1 and H=0, then the effect of do(H=1) versus do(H=0) at each M. Replace the coefficient of M with 40 and repeat: explain which comparison changes.

# Remember

An SCM states mechanisms and background variables.

do(X=x) replaces the equation for X; conditioning selects cases with X=x.

Individual counterfactuals require more information than a comparison of population averages.

# Common mistake

Changing every correlated variable when simulating do(X=x). A surgical intervention changes the assigned mechanism; downstream consequences follow through the remaining equations.

# Research bridge

The arrows sought by discovery methods are useful because they encode claims about mechanisms and possible interventions.

A causal model can connect a graph and distribution to intervention questions when the model's assumptions hold.

# Assumptions

The stated structural equations represent the relevant mechanisms.

The ideal intervention is well defined and leaves the other mechanisms invariant for the question considered.

# Limits

Real interventions can have side effects that a simple do(X=x) model omits.

Observational data may be compatible with several SCMs that imply different interventions or counterfactuals.

# Reading task

Look for the graphical-model discussion and the relationship between causal structure and intervention effects. Translate each unfamiliar symbol into 'which recipe uses which input?'

Write two equations for a system you know, then show exactly which equation an intervention replaces.

# Reflection

Describe a realistic side effect that could make an actual intervention differ from the ideal do operation in your example.

# Referenced readings (external originals)

Causal Inference: What If (2020). Verified public book resource; not represented as one of the user's unlocated local books.. https://miguelhernan.org/whatifbook

Causal discovery and inference: concepts and recent methodological advances (2016). Peer-reviewed review article.. https://doi.org/10.1186/s40535-016-0018-x

CMU 80-516: Causation, Machine Learning, and AI (2025). University course page, Spring 2025; not itself a validation of every research claim.. https://www.andrew.cmu.edu/course/80-516/
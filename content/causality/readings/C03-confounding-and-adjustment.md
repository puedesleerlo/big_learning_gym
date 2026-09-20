# 3. Why group averages can reverse

How can a treatment look worse overall while looking better within each severity group?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Recognize a common cause of treatment and outcome.

Compute a simple standardized comparison using common population weights.

Name exchangeability, positivity, and consistency in plain language.

# Intuition

Suppose the sickest patients are most likely to receive a treatment. Severity influences both treatment and recovery, creating a backdoor route from treatment through severity to outcome. A comparison of treated and untreated patients then mixes the treatment effect with different starting conditions. The treatment can help within both severity groups and still look harmful in the pooled data because the groups contain different kinds of patients.

Adjustment tries to compare outcomes under the same mix of relevant starting conditions. First compare treated and untreated people within each severity group, then average those comparisons using one target population's severity weights. For a binary treatment A, outcome Y, and sufficient pre-treatment covariates Z, the adjustment formula is E[Y under do(A=a)] = sum over z of E[Y | A=a,Z=z] × P(Z=z). The weights represent the target population, rather than a treatment group's accidental composition.

This formula needs substantive assumptions. Conditional exchangeability says the adjusted groups are comparable with respect to their potential outcomes: no relevant residual confounding remains. Positivity says each treatment is possible in the covariate groups whose effects we want to learn. Consistency connects the recorded treatment to the intervention we mean, including a sufficiently clear treatment definition. Measuring a few covariates or obtaining a small p-value does not establish any of these.

# One treatment, two case mixes

Among mild cases, 90 of 100 treated patients recover (90%), versus 720 of 900 untreated patients (80%). Among severe cases, 270 of 900 treated patients recover (30%), versus 20 of 100 untreated patients (20%). Overall, treated recovery is 36% and untreated recovery is 74%. Standardizing both to a population that is half mild and half severe gives treated recovery 0.5×90%+0.5×30%=60%, and untreated recovery 0.5×80%+0.5×20%=50%. The standardized difference is +10 percentage points, if severity is a sufficient adjustment set and the other assumptions hold.

# Try it

Use the within-severity rates in the worked example. Recalculate pooled rates if each treatment group is 50% mild and 50% severe, then compare with the original 10/90 and 90/10 compositions. Keep within-severity rates fixed and explain the reversal.

# Remember

Different case mixes can reverse a pooled comparison.

Use one target population's weights for both treatment alternatives.

Adjustment identifies an effect only under an appropriate graph and substantive assumptions.

# Common mistake

Adjusting for every available variable. A mediator changes the question, and a collider can introduce bias.

# Research bridge

Discovery is often a way to choose which variables could make an observational effect comparison meaningful. This book explains what identification requires after that choice.

Observational data can identify causal effects under consistency, exchangeability, and positivity, along with the relevant estimation conditions.

# Assumptions

No residual confounding after the chosen adjustment for the effect under study.

Both treatment alternatives occur in each relevant covariate group.

Recorded treatment corresponds to a well-defined intervention; interference is absent or appropriately modeled.

# Limits

A graph learned from the same data does not prove that all confounders were measured.

Finite-sample estimation may be unstable even when the identification formula is valid.

# Reading task

Begin with the freely available book's early discussions of causal effects, randomization, and observational studies. Use the current author-hosted version; no chapter or page number is assumed here.

Use the worked example to compute the standardized effect for a population with 80% mild cases. State why a common weighting distribution matters.

# Reflection

In a real decision you care about, which variables exist before treatment and could influence both treatment choice and the outcome?

# Referenced readings (external originals)

Causal Inference: What If (2020). Verified public book resource; not represented as one of the user's unlocated local books.. https://miguelhernan.org/whatifbook

CMU OLI: Causal and Statistical Reasoning (None). Official university course page.. https://www.oli.cmu.edu/courses/causal-and-statistical-reasoning/
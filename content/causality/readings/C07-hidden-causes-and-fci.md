# 7. When important causes are missing

What can a causal graph say when the data do not contain every common cause?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Explain why hidden confounding changes the discovery target.

Distinguish a PAG from a CPDAG.

Interpret arrowheads and circles without inventing probabilities.

# Intuition

Imagine measuring coffee drinking and insomnia but not stressful work. Stress can cause both measured variables. A method that assumes all common causes are observed may try to explain their dependence with a direct connection between the measured variables. A latent-variable method allows that the observed relationship may be generated through unmeasured variables, so its output must represent a different kind of uncertainty.

FCI, fast causal inference, uses conditional-independence information while allowing latent common causes and, in its general formulation, selection effects. Its output is a partial ancestral graph, or PAG, which represents features shared by an equivalence class of maximal ancestral graphs over measured variables. You do not need the full mathematical machinery yet: the essential idea is that its edge marks encode ancestry constraints shared across compatible hidden-variable explanations.

An arrowhead at Y on an X–Y edge rules out Y being an ancestor of X in the represented ancestral-graph sense. A circle means that endpoint mark is unresolved across the class, not that it has a 50% chance of being an arrowhead. In a setting without selection, a bidirected X ↔ Y edge is compatible with latent common causes and rules out either endpoint being an ancestor of the other. It does not name, count, or measure the hidden causes, and a PAG is not a drawing of the full hidden DAG.

# Three explanations for two correlated measurements

With only observed X and Y and no further information, dependence can be compatible with X causing Y, Y causing X, or an unmeasured cause U influencing both. Conditional-independence discovery cannot decide among these stories merely by increasing the sample size. In an appropriate FCI analysis the unresolved relation may be X o–o Y. The circles preserve uncertainty. Additional observed variables, interventions, or justified background constraints may narrow the compatible explanations.

# Try it

Draw X → Y, Y → X, and X ← U → Y. Hide U and record why dependence between X and Y alone cannot distinguish them. Write what extra experiment or measurement could help.

# Remember

Allowing hidden common causes changes the class of causal models under consideration.

A PAG contains ancestral information and unresolved endpoint marks.

FCI can be sound under its assumptions without identifying every direction or hidden variable.

# Common mistake

Reading every FCI connection as a direct causal arrow, or reading a bidirected edge as proof that there is exactly one hidden confounder.

# Research bridge

The paper formalizes how to orient all the information that is identifiable from the relevant equivalence class, while preserving ambiguity caused by latent variables and selection.

Complete orientation rules characterize the invariant endpoint information for the equivalence-class target under the paper's framework.

# Assumptions

An underlying acyclic causal framework with appropriate Markov and faithfulness assumptions.

Correct conditional-independence information for the population-level correctness claim.

Latent confounding and selection are represented by the specified ancestral-graph framework.

# Limits

Finite-sample testing error can corrupt the learned PAG.

A PAG does not generally identify the complete latent DAG or every intervention effect.

Completeness of orientation rules does not mean every edge becomes fully oriented.

# Reading task

Read the abstract and the definitions of ancestral graphs and partial ancestral graphs. Inspect a small example of a circle endpoint before tackling the orientation rules.

Explain in plain language why an unresolved circle can be a correct and useful result.

# Reflection

Which plausible unmeasured common causes would make causal sufficiency a risky assumption for your dataset?

# Referenced readings (external originals)

On the completeness of orientation rules for causal discovery in the presence of latent confounders and selection bias (2008). Peer-reviewed Artificial Intelligence article.. https://doi.org/10.1016/j.artint.2008.08.001

Causal discovery and inference: concepts and recent methodological advances (2016). Peer-reviewed review article.. https://doi.org/10.1186/s40535-016-0018-x

Causal-learn: Causal Discovery in Python (2024). Peer-reviewed JMLR paper; code and online platform may evolve.. https://www.jmlr.org/papers/v25/23-0970.html

py-why/causal-learn (None). Official living repository; source consulted September 2026.. https://github.com/py-why/causal-learn
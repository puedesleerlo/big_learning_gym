# 4. Three little graphs that change everything

When does controlling for another variable help, and when can it manufacture an association?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Recognize chains, forks, and colliders.

Predict how conditioning changes whether a path is open.

Distinguish estimating a total effect from conditioning on a mediator.

# Intuition

A chain looks like X → M → Y: exercise changes fitness, which changes endurance. A fork looks like X ← Z → Y: hot weather increases both ice cream sales and swimming. In each case, the middle variable is a noncollider on the path. Conditioning on that middle variable blocks that path. Blocking a confounding fork can help estimate an effect. Blocking a causal chain removes part of the total effect we may want to count.

A collider looks like X → S ← Y. Imagine two independent abilities, sports skill and academic skill, either of which can help a student win a scholarship. In the full population the abilities need not be related. Among scholarship winners, a student with less of one skill may tend to have more of the other, because either can explain selection. Conditioning on their common effect creates an association. Conditioning on a descendant of a collider can also open its path.

D-separation is the graph rule that generalizes these three patterns. Relative to a conditioning set, a path is blocked if it contains a conditioned noncollider, or a collider for which neither the collider nor any descendant is conditioned on. A path can run along or against arrow directions; it is the local collider pattern that matters. Under the causal Markov assumption, d-separation implies a corresponding conditional independence in the distribution.

# A scholarship makes independent skills look opposed

Suppose sports skill X and academic skill Y are independent binary variables, each equally likely to be high. A scholarship S is awarded if at least one skill is high. Before selection, P(Y=high | X=high)=P(Y=high | X=low)=1/2. Among winners, if X is low then Y must be high; if X is high, Y is high only half the time. Conditioning on S created a negative association, although changing sports skill does not change academic skill in this toy model.

# Try it

List the four equally likely combinations of high/low sports and academic skill. Compare P(academic=high | sports=high) with P(academic=high | sports=low) before selection. Remove the low/low combination to select scholarship winners, recalculate, and explain the induced association.

# Remember

Conditioning blocks a chain or fork at its middle noncollider.

Conditioning on a collider or its descendant can open a previously blocked path.

Whether to adjust depends on the graph, conditioning set, and target effect.

# Common mistake

Calling a variable 'good to control for' based only on its predictive power. Its position in the causal graph matters.

# Research bridge

PC uses conditional independence patterns to remove edges and identify unshielded colliders. The three-variable reasoning you just learned is its core intuition.

In appropriate settings, conditional independence information constrains an equivalence class of DAGs, and collider information helps orient it.

# Assumptions

Causal Markov connects graphical separation to independence.

Faithfulness excludes extra independences caused by special parameter cancellations.

The standard PC causal interpretation assumes no latent common causes among the measured variables and an acyclic model.

# Limits

Statistical independence tests are imperfect at finite sample sizes.

A dependence or an independence alone does not label a variable as a mediator or confounder.

# Reading task

Read the algorithm overview and its discussion of skeleton estimation. First identify what a separating set does; leave the high-dimensional proof for later.

Compare X → M → Y with X → M ← Y. Predict whether X and Y are independent before and after conditioning on M, assuming faithfulness and no other paths.

# Reflection

Think of a dataset assembled only from successful applicants, hospitalized patients, or published papers. Could its inclusion rule be a collider?

# Referenced readings (external originals)

Causal Inference: What If (2020). Verified public book resource; not represented as one of the user's unlocated local books.. https://miguelhernan.org/whatifbook

Causal discovery and inference: concepts and recent methodological advances (2016). Peer-reviewed review article.. https://doi.org/10.1186/s40535-016-0018-x

Estimating High-Dimensional Directed Acyclic Graphs with the PC-Algorithm (2007). Peer-reviewed JMLR article.. https://www.jmlr.org/papers/v8/kalisch07a.html
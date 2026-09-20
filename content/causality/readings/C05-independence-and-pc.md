# 5. Learning what a graph cannot yet tell you

How can an algorithm learn useful causal structure without choosing every arrow?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Explain the distinct roles of Markov, faithfulness, and causal sufficiency.

Read a CPDAG as a set of compatible DAGs.

Describe PC's skeleton, collider, and orientation steps.

# Intuition

PC starts with candidate connections and asks whether pairs of variables become independent after conditioning on other variables. If it finds a separating set, it removes the connection. It then looks for unshielded triples: X and Y are each connected to M, but X and Y are not connected. If M is absent from their separating set, this supports the collider X → M ← Y under the algorithm's assumptions. Further orientation rules propagate what follows without introducing forbidden colliders or cycles.

Three assumptions do different jobs. The causal Markov condition says graphically separated variables are independent in the distribution. Faithfulness says the distribution does not contain extra independences caused by special cancellations or other coincidences. Causal sufficiency says the modeled measured variables have no unmeasured common causes. Standard causal PC also uses an acyclic causal graph. These are substantive claims about the data-generating process, not interchangeable names for a good statistical fit.

Even perfect independence information cannot always choose a unique DAG. X → M → Y, X ← M → Y, and X ← M ← Y have the same skeleton and no unshielded collider, so they imply the same conditional independences. A completed partially directed acyclic graph, or CPDAG, represents this Markov equivalence class. Directed edges are shared by all class members; undirected edges have different directions in different members. An undirected edge is a meaningful statement of unresolved direction.

# Three stories, one independence pattern

Suppose X and Y are dependent, but independent given M, and both X–M and M–Y remain connected. The skeleton is X–M–Y. With no other variables or background constraints, the chain X → M → Y, the reverse chain, and the fork are compatible. The collider X → M ← Y is not compatible with this faithful pattern. The CPDAG keeps both edges undirected. More observational samples improve estimation of the pattern, but do not by themselves distinguish those three stories.

# Try it

On paper, draw the three noncollider DAGs on X–M–Y. List their implied marginal and conditional independences. Then draw the collider and identify what changes. If you run PC later, compare its output with this known population target.

# Remember

A valid output may deliberately leave directions unresolved.

Markov, faithfulness, and causal sufficiency are different assumptions.

Failing to reject an independence-test null is not proof of independence.

# Common mistake

Interpreting p>0.05 as proof of independence, or interpreting a CPDAG's undirected edge as no causal connection.

# Research bridge

This paper links a concrete discovery procedure to conditions under which estimation can work even with many variables.

PC can consistently estimate the relevant equivalence class under the paper's high-dimensional Gaussian, sparsity, and regularity conditions.

# Assumptions

A DAG model, causal Markov, faithfulness, and appropriate no-hidden-common-cause interpretation.

For the cited consistency result: Gaussianity, sparsity, and additional quantitative regularity conditions.

Conditional independence tests and their settings must suit the data.

# Limits

The theorem is not a guarantee that every finite-data output is correct.

Markov equivalence can remain even with unlimited observational data.

Small samples, weak associations, selection, or invalid tests can mislead the search.

# Reading task

Read the abstract, algorithm description, and assumptions. For each theorem, ask whether it concerns the population limit or a particular sample size.

Explain why more samples and an intervention address two different sources of uncertainty: estimation error and equivalence-class ambiguity.

# Reflection

Which ambiguity in your own problem might persist even if you collected ten times more observational data?

# Referenced readings (external originals)

Estimating High-Dimensional Directed Acyclic Graphs with the PC-Algorithm (2007). Peer-reviewed JMLR article.. https://www.jmlr.org/papers/v8/kalisch07a.html

Causal-learn: Causal Discovery in Python (2024). Peer-reviewed JMLR paper; code and online platform may evolve.. https://www.jmlr.org/papers/v25/23-0970.html

py-why/causal-learn (None). Official living repository; source consulted September 2026.. https://github.com/py-why/causal-learn

Causal discovery and inference: concepts and recent methodological advances (2016). Peer-reviewed review article.. https://doi.org/10.1186/s40535-016-0018-x
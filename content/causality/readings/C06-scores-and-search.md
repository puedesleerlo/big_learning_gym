# 6. Searching for a good graph efficiently

How do GES and BOSS search enormous spaces without mistaking a high score for truth?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Explain why a graph score balances fit and complexity.

Distinguish equivalence-class search from ordering search.

Read asymptotic and empirical performance claims with their conditions.

# Intuition

With many variables, listing every possible DAG is impractical. Score-based methods define a criterion that rewards explaining the data while penalizing unnecessary complexity, then search for a graph with a good score. A familiar example is BIC, which combines likelihood with a penalty that grows with the number of parameters and sample size. The likelihood family is part of the model: a linear Gaussian score is not automatically appropriate for every dataset.

Greedy equivalence search, or GES, searches over equivalence classes, adding and then deleting connections through valid operators. BOSS, best order score search, instead searches variable orderings. An ordering says which variables may precede others; a parent-selection procedure then builds a graph consistent with that ordering. Efficiently reusing computations makes exploring many orderings faster. These are different search strategies, not different definitions of causality.

A high score supports a model relative to the score, candidates, assumptions, and data. It is not a direct measurement of causal truth. Consistency theorems describe what happens as samples grow under stated conditions. Benchmarks describe performance in evaluated finite settings. For the cited BOSS paper, the asymptotic correctness argument uses an optional backward equivalence search step; the reported experiments omitted that step. It matters which algorithm configuration a theoretical statement actually covers.

# Fit improves, but the graph gets larger

Imagine two candidate models for 500 independent observations. Model A has a log-likelihood advantage of only 1 over model B but uses two extra parameters. With the convention BIC score = log-likelihood − (number of parameters × log n)/2, A's score advantage is 1 − log(500), about −5.21. B wins this criterion despite fitting slightly better in-sample. The calculation selects a model under the chosen likelihood; it does not establish that the true process has no hidden common causes.

# Try it

Calculate the BIC comparison in the worked example. Then write an experiment plan comparing GES and BOSS on one simulated DAG: same samples, suitable score, recorded settings, and both adjacency and orientation errors. A notebook is optional; the plan itself is the exercise.

# Remember

The score, likelihood family, and search algorithm play different roles.

A method's theoretical guarantee can depend on a specific option or search step.

A strong benchmark result does not eliminate assumptions or Markov equivalence.

# Common mistake

Reporting 'BOSS found the true graph' because one run had the best BIC or because the paper's simulations were accurate.

# Research bridge

It shows how changing the search machinery can make causal discovery scale while leaving the need for scientific assumptions intact.

BOSS uses order search and grow-shrink trees to obtain strong speed and accuracy in its evaluated settings; its cited asymptotic correctness result concerns a variant with optional BES enabled.

# Assumptions

The relevant correctness statement assumes an acyclic causally sufficient setting, Markov and faithfulness, IID data, and a suitable exponential-family/BIC setup.

The theorem's BOSS configuration includes the optional backward equivalence search step.

# Limits

The reported no-BES experiments and the theorem-covered configuration should not be conflated.

Benchmark performance is limited to evaluated graph families, sample sizes, and settings.

Score equivalence can leave causal directions unresolved.

# Reading task

Read the search overview, then the statement of Proposition 2 and the experimental configuration. Locate where optional backward equivalence search is used or omitted.

Write one sentence about the theorem-covered algorithm and a separate sentence about the empirically evaluated configuration, without making either stronger than the source.

# Reflection

When reading a new algorithm paper, which is its main contribution: stronger identification, better search, better tests, or better empirical performance?

# Referenced readings (external originals)

Optimal Structure Identification With Greedy Search (2002). Peer-reviewed JMLR article; asymptotic results are not finite-sample guarantees.. https://jmlr.csail.mit.edu/papers/v3/chickering02b.html

Fast Scalable and Accurate Discovery of DAGs Using the Best Order Score Search and Grow Shrink Trees (2023). Peer-reviewed NeurIPS 2023 paper; empirical comparisons apply to the evaluated settings.. https://proceedings.neurips.cc/paper_files/paper/2023/hash/c9cde817d04811ba28e44071bd9f76a5-Abstract-Conference.html

Causal-learn: Causal Discovery in Python (2024). Peer-reviewed JMLR paper; code and online platform may evolve.. https://www.jmlr.org/papers/v25/23-0970.html

py-why/causal-learn (None). Official living repository; source consulted September 2026.. https://github.com/py-why/causal-learn
# 11. Reading a new discovery algorithm

How can search and targeted tests make discovery faster without making claims stronger than the evidence?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Explain the purpose of a score-search plus independence-testing pipeline.

Distinguish correctness claims from heuristic performance claims.

Check whether a benchmark's target matches the algorithm's output.

# Intuition

An algorithm that asks every possible conditional-independence question can become expensive as the number of variables grows. A hybrid approach first uses an efficient score search to propose useful structure, then applies tests and orientation rules designed for the latent-variable setting. The first stage can focus effort; the later stages determine which conclusions remain justified. You should ask whether an early mistake can be corrected and which theoretical conditions cover the whole pipeline.

The 2025 preprint studied here develops BOSS-FCI, GRaSP-FCI, and targeted-testing approaches such as FCIT, alongside explicitly heuristic variants. This is active research, so method names are less important than the logic: what work is avoided, what information is preserved, and what assumptions make that safe? A variant can perform well empirically without sharing an FCI-style soundness guarantee. Keep each variant's theory attached to that variant.

Benchmark interpretation is another causal reasoning skill. A method may output a PAG, while a performance figure evaluates a property of the generating DAG. Adjacency accuracy, endpoint accuracy, ancestry accuracy, and runtime measure different things. In this preprint's 100-node experiment, some path-related metrics use the generating DAG rather than the true PAG. That distinction should inform your reading, because compatibility with a data-generating graph and recovery of the identifiable equivalence-class target are not identical questions.

# The faster answer may answer a different scoring question

Suppose a hybrid method takes 10 seconds and an FCI baseline takes 40 seconds on the same simulated data. The hybrid has better adjacency precision but worse endpoint recall. This supports a speed/structure tradeoff in that protocol, not a universal win. If an endpoint remains unidentifiable in the population PAG, scoring against one fully oriented generating DAG can also penalize an appropriately unresolved result. Always inspect the target graph and metric definition before ranking methods.

# Try it

Create a four-line evaluation card for one algorithm: input assumptions, output graph type, runtime/accuracy metrics, and theoretical status. Use the linked preprint to fill it, then mark which statements are theorem claims and which are experimental observations.

# Remember

Separate the proposed speedup from the scientific information it preserves.

Sound variants and heuristic variants need different claims.

The metric, target graph, and protocol are part of the result.

# Common mistake

Merging several algorithms in one paper into a single claim that all are faster, more accurate, and guaranteed to be correct.

# Research bridge

It is a concrete bridge from the classic PC/FCI and score-search ideas to current attempts at scalable latent-variable discovery.

The preprint combines score-search proposals and targeted testing to improve efficiency in evaluated latent-variable discovery settings while distinguishing FCI-style sound methods from heuristic variants.

# Assumptions

Soundness claims depend on the specific algorithm, graph model, and valid independence information.

Finite-sample experiments use their documented scores, test settings, depth limits, and data-generating families.

# Limits

This source is an arXiv preprint, version 3; peer review is not asserted.

LV-Dumb (also called BOSS-POD) should not inherit an FCI-soundness claim merely because it appears in the same paper.

In the 100-node section, path metrics evaluated against the generating DAG should not be mistaken for full true-PAG recovery.

Empirical speed/accuracy does not establish universal superiority or validate assumptions on a new dataset.

# Reading task

Read the algorithm comparison and theoretical-status discussion before the benchmark plots. Inspect the experimental definitions of path metrics and their target graphs.

Choose one method and write a 120-word review stating its input, output, promise, assumptions, empirical evidence, and one unresolved question.

# Reflection

When does it make sense to use a heuristic in your work? What validation would make its limitations visible?

# Referenced readings (external originals)

Efficient Latent Variable Causal Discovery: Combining Score Search and Targeted Testing (2025). arXiv preprint as verified for this lab; no claim of peer review or universal superiority.. https://arxiv.org/abs/2510.04263v3

Fast Scalable and Accurate Discovery of DAGs Using the Best Order Score Search and Grow Shrink Trees (2023). Peer-reviewed NeurIPS 2023 paper; empirical comparisons apply to the evaluated settings.. https://proceedings.neurips.cc/paper_files/paper/2023/hash/c9cde817d04811ba28e44071bd9f76a5-Abstract-Conference.html

On the completeness of orientation rules for causal discovery in the presence of latent confounders and selection bias (2008). Peer-reviewed Artificial Intelligence article.. https://doi.org/10.1016/j.artint.2008.08.001

Tetrad: Papers and Books (None). Living secondary index; primary papers are cited separately.. https://tetrad-manual.readthedocs.io/en/latest/papers-and-books.html
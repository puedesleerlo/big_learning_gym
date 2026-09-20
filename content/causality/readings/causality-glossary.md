# Causality glossary

Original AI-assisted teaching definitions.

# Association

A statistical relationship between observed variables. It does not alone establish what an intervention would change.

# Intervention

A specified action that changes a variable's generating mechanism. Its alternatives and side effects must be defined.

# do(X=x)

An ideal intervention that replaces the structural equation for X with X=x while retaining the other mechanisms.

# Conditioning

Restricting a distribution to cases with specified observed values, such as comparing people who naturally received a treatment.

# Counterfactual

An outcome under an alternative action for a unit or population, defined by a causal model or potential-outcome framework.

# Estimand

The exact quantity a study aims to learn, such as an average treatment effect for a defined population and period.

# SCM

Structural causal model: equations describing how variables are generated from their direct causes and background disturbances.

# DAG

Directed acyclic graph: a graph with arrows and no directed cycle.

# Confounder

A common cause relevant to the treatment-outcome comparison; confounding leaves noncausal routes in that comparison.

# Mediator

A variable on a directed causal path between a cause and an outcome.

# Collider

A variable with two incoming arrows along the path being considered, as in X → S ← Y.

# Selection bias

Bias from the process determining which cases are observed or analyzed; conditioning on selection can open collider paths.

# Adjustment

Using an appropriate set of variables to connect observational comparisons to a defined causal effect under assumptions.

# Exchangeability

A condition under which treatment groups, perhaps after conditioning, are comparable with respect to the relevant potential outcomes.

# Positivity

Each treatment alternative has nonzero probability in the covariate groups needed for the target comparison.

# Consistency

A unit's observed outcome agrees with its potential outcome under the treatment version actually received, with the intervention clearly defined.

# D-separation

A graph criterion for whether conditioning blocks all paths between variable sets. Under Markov, it implies conditional independence.

# Conditional independence

Once specified variables are given, knowing one variable adds no distributional information about another.

# Causal Markov condition

The causal graph's d-separations imply corresponding conditional independences in the distribution.

# Faithfulness

The distribution has no additional conditional independences beyond those implied by the graph's d-separations.

# Causal sufficiency

Within the modeled variable set, no common causes of measured variables are left unmeasured.

# Markov equivalence

DAGs that imply the same conditional independence relations; their observational independence information cannot distinguish them.

# CPDAG

Completed partially directed acyclic graph representing a Markov equivalence class of DAGs, with invariant arrows and unresolved undirected edges.

# Latent variable

A variable in the causal system that is not directly observed in the analyzed data.

# PAG

Partial ancestral graph representing invariant endpoint information across an equivalence class of ancestral graphs, allowing hidden causes and selection in the appropriate framework.

# Circle endpoint

A PAG mark indicating an unresolved endpoint across the represented equivalence class, not a probability.

# BIC

Bayesian information criterion: a model-comparison criterion combining likelihood and a parameter-count penalty; sign conventions vary.

# Consistency of an estimator

Convergence to its target as sample size grows under specified conditions; different from treatment consistency.

# Non-Gaussian disturbance

A structural error or background term whose distribution is not Gaussian; LiNGAM exploits this along with other assumptions.

# Distribution shift

A change in the data distribution across settings or time; it need not mean a specific causal mechanism was intervened on.

# Mechanism invariance

Stability of a specified causal generating rule across the environments being considered.

# Granger predictability

Added predictive information from the past of one variable about another, relative to a specified information set and model; causal interpretation needs additional assumptions.

# Identifiability

Whether the available distributional information and assumptions determine the target quantity or structure, potentially up to stated ambiguities.

# Causal representation learning

Learning latent causal factors and aspects of their relationships from observations such as pixels or embeddings.

# Moralized graph

An undirected graph formed from a DAG by joining co-parents and removing arrow directions.

# Componentwise transformation

A separate transformation of each coordinate, such as an invertible rescaling; it does not freely mix different factors.

# Ablation

An experiment removing or varying a component to assess its contribution, with comparisons interpreted under the changed conditions.

# Preprint

A publicly shared research manuscript for which peer-reviewed publication is not implied by its preprint status.

# Auxiliary supervision

Additional labels, masks, or other training information beyond the main inputs and targets; unequal access can affect comparisons.

# Bootstrap edge frequency

How often an edge appears across resampled analyses under a procedure; not automatically the probability that the edge is causally true.
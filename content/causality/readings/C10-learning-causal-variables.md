# 10. Before the arrows: what are the variables?

If your data are images or embeddings, where do the causal variables come from?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Distinguish observed measurements from latent causal factors.

Explain why reconstructing data does not identify a causal representation.

Interpret moralized-graph recovery and identification up to transformations.

# Intuition

So far our columns had clear names: treatment, severity, price, recovery. In an image, the columns are pixels. The variables we might want to intervene on—lighting, object position, material, camera angle—are hidden factors that combine to generate the pixels. Causal representation learning tries to recover useful causal factors and their structure from such observations. This adds a problem before graph discovery: choosing the right variables.

Reconstructing the image accurately is not enough. Many different hidden coordinate systems can generate the same observed images. One representation may mix lighting and material into each coordinate, while another separates them. Both can predict pixels well. Identification means proving that the data and assumptions distinguish the desired representation, perhaps only up to a limited ambiguity. 'Up to a componentwise transformation' means each recovered factor can be individually rescaled or transformed; it is weaker than recovering the physical units exactly.

The cited multiple-distribution paper uses information from changing environments and structural restrictions. Its general result includes recovery of a moralized graph, not unrestricted recovery of every directed latent edge. Moralization drops arrow directions and connects parents that share a child. Thus distinct directed structures can have the same moralized graph. A frontier result can be substantial precisely because it states which part of the problem becomes identifiable and which part remains unresolved.

# A collider becomes a triangle after moralization

Consider latent factors A → C ← B with no A–B edge. Moralization drops the arrowheads on A–C and B–C, then adds A–B because A and B are parents of the same child. The result is an undirected triangle. Recovering this triangle alone does not show that A directly causes B; that edge may have been added by moralization. Likewise, a recovered factor related monotonically to brightness need not equal brightness measured in physical units.

# Try it

Draw A → C ← B and moralize it by removing directions and joining co-parents. Draw a second DAG with the same moralized triangle. State what the shared undirected graph cannot tell you.

# Remember

Causal discovery assumes variables; causal representation learning also tries to recover them.

Prediction and reconstruction accuracy do not by themselves identify causal factors.

A moralized graph and a full directed latent DAG are different targets.

# Common mistake

Reading 'identifiable causal representation' as 'all true variables, arrows, and intervention effects are recovered without assumptions'.

# Research bridge

It connects causal discovery to representation learning while making the identifiability target explicit.

Under the paper's sparsity, sufficiently rich distribution changes, and other structural conditions, its general setting identifies the moralized graph; under additional graph-dependent conditions, some latent variables can be recovered up to componentwise transformations.

# Assumptions

The observation/mixing model meets the stated smoothness and invertibility conditions.

Changes across distributions are sufficiently rich for the relevant identification result.

The latent structure satisfies the specified sparsity and appropriate weaker-faithfulness conditions.

# Limits

The general result is narrower than full recovery of the directed latent DAG.

Recovering some factors up to transformations does not recover physical units or every factor exactly.

Real environments may not supply the diversity or structural conditions required.

# Reading task

Read the problem setup, the main identifiability claims, and the assumptions. Circle every phrase specifying which graph or variables are recovered.

Translate the paper's recovery target into a three-item list: what is recovered, what equivalences remain, and what is not generally promised.

# Reflection

If a model gives you a hidden variable called 'risk', what evidence would make you believe that changing it corresponds to a coherent real-world intervention?

# Referenced readings (external originals)

Causal Representation Learning from Multiple Distributions: A General Setting (2024). Peer-reviewed ICML 2024 paper; does not generally identify the full directed latent graph.. https://proceedings.mlr.press/v235/zhang24br.html

CMU 80-516: Causation, Machine Learning, and AI (2025). University course page, Spring 2025; not itself a validation of every research claim.. https://www.andrew.cmu.edu/course/80-516/

Causal discovery and inference: concepts and recent methodological advances (2016). Peer-reviewed review article.. https://doi.org/10.1186/s40535-016-0018-x
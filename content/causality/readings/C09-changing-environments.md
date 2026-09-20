# 9. Learning from a world that changes

Can distribution shift become evidence about mechanisms instead of just a modeling problem?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Distinguish a changing cause distribution from a changing causal mechanism.

Explain how context or time can enter a discovery model.

State why distribution shifts require assumptions before they can orient arrows.

# Intuition

Suppose several shops use different prices, but customers respond to a given price in the same way everywhere. The distribution of price changes across shops, while the relationship that generates demand from price stays stable. Now imagine a heat wave changes how strongly customers respond to price. That is a change in the demand mechanism. Both situations can change observed demand, but for different reasons.

CD-NOD studies heterogeneous or nonstationary data: data from different domains, conditions, or times whose distributions are not constant. A context or time index helps detect which variables' generating mechanisms change. Under additional assumptions, patterns of mechanism changes can also provide direction information. The central idea is that cause and effect mechanisms can have a different pattern of changes than the factors in an incorrect reversed description.

Context is not automatically an intervention variable. A hospital label could stand for differences in treatment policy, patient severity, measurement equipment, and selection all at once. Calendar time can accompany autocorrelation, feedback, or several simultaneous changes. A method must specify how those changes relate to its causal model. The claim 'the distribution shifted' is much weaker than 'this shift identifies the direction'.

# A new customer mix versus a new response rule

Write demand D=100−2P+N, where P is price and N is independent demand noise. Across two shops, the price distribution differs but the coefficient −2 and noise distribution stay the same. P(D | P) remains stable under this toy model even while average demand changes. If the second shop instead has D=100−5P+N, the response mechanism changed too. Real shops may also differ in unmeasured customer preferences, so their labels alone do not prove these equations.

# Try it

For D=100−2P+N with mean-zero independent N, compare a shop with mean price 10 to a shop with mean price 20. Compute expected demand, then explain whether P(D | P) changed. Repeat conceptually after changing the coefficient from −2 to −5.

# Remember

A marginal distribution can change because inputs change or because its own mechanism changes.

Multiple environments can add causal information under explicit structure and change assumptions.

Time order and predictive advantage alone do not remove confounding.

# Common mistake

Calling any distribution difference a natural experiment, or assuming a time index captures every relevant change.

# Research bridge

The paper turns changes across domains or time into a potential source of discovery information, connecting causality to practical distribution shift.

Under specified structural and change assumptions, heterogeneous/nonstationary data can help detect changing mechanisms and orient some causal relations.

# Assumptions

A suitable causal graph augmented with context or time, plus the paper's Markov/faithfulness and regularity conditions.

The orientation procedure needs appropriate assumptions about how causal modules change, including independence-of-change conditions where used.

The context variable and test procedure must fit the heterogeneity in the data.

# Limits

Arbitrary shifts do not identify a unique causal graph.

Unmodeled selection, hidden context effects, or simultaneous dependent mechanism changes can undermine interpretation.

Time-dependent prediction such as Granger predictability is not by itself an identified intervention effect.

# Reading task

Read the motivating examples and the distinction between changing distributions and changing causal modules. Then examine what the context index represents.

For a proposed multi-environment dataset, list what the environment label could change and distinguish measured changes from assumptions about stable mechanisms.

# Reflection

What are the environments in a problem you know: locations, policies, seasons, people, or devices? Which mechanisms might remain stable?

# Referenced readings (external originals)

Causal Discovery from Heterogeneous/Nonstationary Data (2020). Peer-reviewed JMLR article; cite 2020 metadata rather than the inconsistent catalog entry.. https://www.jmlr.org/papers/v21/19-232.html

Causal-learn: Causal Discovery in Python (2024). Peer-reviewed JMLR paper; code and online platform may evolve.. https://www.jmlr.org/papers/v25/23-0970.html

CMU 80-516: Causation, Machine Learning, and AI (2025). University course page, Spring 2025; not itself a validation of every research claim.. https://www.andrew.cmu.edu/course/80-516/
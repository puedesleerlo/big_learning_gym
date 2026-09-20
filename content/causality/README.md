# Causality: from first questions to frontier research

This is an original, beginner-oriented curriculum manifest for the existing Learning Gym. The JSON is the canonical content: 12 lessons, 12 immediate checkpoints, 24 additional practice items, 19 source records, a 40-term glossary, and a capstone. Suggested lesson time totals 365 minutes, before optional paper reading. Time estimates support planning; elapsed time, page views, and completion clicks do not establish mastery.

The learning path has four foundations lessons on causal questions, interventions, adjustment, and graphical paths; four discovery lessons on PC, score search, FCI, and LiNGAM; and four frontier lessons on changing environments, causal representation learning, hybrid latent discovery, and auditing causal AI claims. Prerequisite IDs are explicit. Each lesson offers a concrete question, original explanations, a worked example, a paper bridge, an exercise, a checkpoint, and reflection.

Experiments are self-contained calculations, graph exercises, or research evaluation plans. They can be completed in the current platform without an external notebook or new application. A guided interface may make the same tasks interactive, but the text does not require bespoke controls. Simulated examples are labeled toy worlds with stated generating mechanisms; their truth is not attributed to real-world evidence.

## Assessment contract

Each lesson has one additional multiple-choice question and one open transfer task. Practice items follow `gym.contracts.GeneratedItem`, except `source_fragment_ids` is supplied by the importer after creating the corresponding instructional source. Each item names the lesson capability. Open tasks have an example answer, three task-specific criteria, weights of 0.4/0.4/0.2, and observable full-credit anchors. Scores should assess reasoning about the case, not merely the presence of terminology.

The checkpoint is separate from the two practice items. It may provide immediate feedback or become another practice item when populating the existing exercise bank. Completion or checkpoint exposure should not silently substitute for an independently answered transfer task. Preserve initial answers, feedback, revisions, and source/rubric versions when using them as evidence of learning.

## Source provenance

Sources were checked through primary publication pages, official code, university course pages, and company articles for this September 2026 lab. Explanations are original synthesis, not copied textbook chapters or paper excerpts. Source records distinguish peer-reviewed papers, research preprints, living software, courses, a public book, and company interpretations.

The user mentioned two books, but no corresponding local files or saved attachments were located. [Hernán and Robins, Causal Inference: What If](https://miguelhernan.org/whatifbook) is included as a verified public supplemental resource. It is not represented as one of those unlocated books. No chapter or page provenance has been invented. The original book files can later be ingested and linked to the same lessons through the platform's normal material workflow.

The [causal-learn repository](https://github.com/py-why/causal-learn) anchors the software reading. The [Tetrad bibliography](https://tetrad-manual.readthedocs.io/en/latest/papers-and-books.html) is a navigation aid; original publication records determine paper metadata and claims. The [CausalLearn platform](https://causallearn.com) is linked as a relevant interface, but its analyses were not independently evaluated in this source pass.

Several qualifications are deliberately prominent:

- PC's CPDAG and FCI's PAG are distinct outputs; unresolved endpoints are not numerical probabilities.
- Markov, faithfulness, causal sufficiency, positivity, and treatment consistency have different meanings. Estimator consistency is separately defined.
- BOSS's cited asymptotic guarantee covers the variant with optional backward equivalence search; its reported experimental configuration omitted that step.
- The ICML 2024 causal representation result recovers a moralized graph under stated conditions. Recovery of some individual factors requires additional graph-dependent conditions and retains transformation ambiguities.
- The hybrid latent-discovery preprint is cited at version 3 with Joseph Ramsey, Bryan Andrews, and Peter Spirtes. LV-Dumb and BOSS-POD refer to the same heuristic variant; its guarantees must not be conflated with FCI-style sound variants.
- The 2026 CD-LAM preprint and Aether's corresponding company interpretation are separate sources. The capstone checks the action-following evaluation, training resources, and auxiliary masks/labels before generalizing an efficiency claim.
- Granger predictability, a strong benchmark score, a bootstrap edge frequency, and a successful prediction do not by themselves establish a causal intervention effect.

## Validation

The manifest was parsed as JSON and every practice item validated with the existing `GeneratedItem` contract after injecting a placeholder fragment ID. All 12 prerequisite lists point to prior lessons, source IDs and paper bridges resolve, answer keys match option labels, and open rubric weights sum to one. Worked numerical examples were checked. An independent research agent reviewed the first four and final four lessons for substantive source and reasoning errors; the remaining discovery lessons received local scientific review.

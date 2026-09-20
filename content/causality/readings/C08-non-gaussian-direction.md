# 8. Extra structure can reveal direction

Can assumptions about how effects are generated reveal arrows that independence alone leaves ambiguous?

Original teaching notes prepared with AI assistance for this Learning Gym. These are explanatory material, not a copy of the referenced publications.

# What you will learn

Explain LiNGAM's linear, acyclic, independent non-Gaussian noise assumptions.

Distinguish residual independence from zero residual correlation.

Identify why hidden confounding threatens the basic LiNGAM model.

# Intuition

Conditional-independence methods use one kind of information: which variables separate after conditioning. Functional-model methods use additional information about the shape of the generating process. In a simple model Y=aX+N, the noise N represents influences on Y that are independent of X. If a reverse model X=bY+R cannot make R independent of Y under the same model class, the two directions are statistically distinguishable.

LiNGAM uses linear equations, an acyclic graph, mutually independent non-Gaussian disturbances, and no hidden confounding in its basic model. Non-Gaussian means the disturbances are not described by the usual bell-shaped normal distribution. Under these assumptions, information in the full distribution can identify directions that covariance or conditional-independence patterns alone cannot. The gain comes from stronger assumptions, not from bypassing the need for assumptions.

Regression residuals require careful interpretation. Ordinary least squares makes residuals uncorrelated with the fitted predictor in the sample under its usual construction. That algebraic fact does not make them independent. Independence excludes all statistical dependence, including nonlinear dependence. In a joint Gaussian setting, covariance-based relationships lack the non-Gaussian information exploited here; simply fitting two regressions and comparing residual correlations will not reproduce LiNGAM's identification argument.

# A bell-shaped special case hides direction

Consider X=Nx and Y=2X+Ny with independent non-Gaussian disturbances. The correct-direction residual Y−2X is Ny and is independent of X by construction. Regressing X on Y generally does not produce a residual independent of Y in this model. If both disturbances instead are Gaussian, linear Gaussian models can admit independent residual descriptions in both directions. The difference explains why the noise assumption matters, rather than serving as a minor implementation detail.

# Try it

Write Y=2X+N and identify what would make N independent of X. Contrast this with a hidden variable U that affects both X and Y. If using a notebook, compare residual dependence in both directions under non-Gaussian and Gaussian simulated noise; record the generating assumptions.

# Remember

Stronger functional assumptions can distinguish observationally equivalent causal directions.

The basic LiNGAM model excludes hidden confounding and feedback.

Uncorrelated residuals are weaker evidence than independent residuals.

# Common mistake

Using a normality test on the observed columns as a complete validation of LiNGAM. Its assumptions concern the structural disturbances and the joint generating model.

# Research bridge

This classic paper demonstrates that identification can improve when we move beyond independence patterns and specify a functional and noise model.

A linear acyclic model with independent non-Gaussian disturbances and no hidden confounding can be identifiable beyond the usual conditional-independence equivalence class.

# Assumptions

Linear structural relations and acyclicity.

Mutually independent non-Gaussian disturbances under the model's identifiability conditions.

No unmeasured common causes in the basic model.

# Limits

Misspecified nonlinear relations, dependent noise, latent confounding, or cycles can invalidate the interpretation.

Finite-data estimation remains imperfect.

Residual noncorrelation does not validate noise independence.

# Reading task

Read the model assumptions and the two-variable motivation before the ICA-based estimation details.

Name the additional assumptions that buy direction information compared with ordinary PC, and describe a domain where one of them is doubtful.

# Reflection

Would you trust linear relations and independent structural disturbances in your setting? State one reason for and one reason against.

# Referenced readings (external originals)

A Linear Non-Gaussian Acyclic Model for Causal Discovery (2006). Peer-reviewed JMLR article.. https://jmlr.org/papers/volume7/shimizu06a/shimizu06a.pdf

Causal-learn: Causal Discovery in Python (2024). Peer-reviewed JMLR paper; code and online platform may evolve.. https://www.jmlr.org/papers/v25/23-0970.html

Causal discovery and inference: concepts and recent methodological advances (2016). Peer-reviewed review article.. https://doi.org/10.1186/s40535-016-0018-x
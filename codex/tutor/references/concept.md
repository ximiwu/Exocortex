# Core Concepts Extraction (from input/input.md)

This document extracts *core concepts* (minimal, reusable knowledge units) from the provided notes, and states why each counts as core. Source localization is given as **Part / Section / Definition-Theorem-Lemma ID**.

## Core Concepts (sorted by importance)

### 1) Norm and Normed Vector Space (Definition)

- **Type:** Definition (structure on a vector space)
- **Localization:** Part 1, Section 3  Norm, *Definition 2.1.1*
- **What it solves / Intuition:** A norm generalizes length to abstract vector spaces, enabling size comparison, error measurement, and geometric reasoning. It is the entry point to topology (limits, continuity) on abstract spaces.
- **Mathematical form:** A map $\|\cdot\|:V\to\mathbb{R}$ such that for all $v,w\in V$, $\alpha\in\mathbb{C}$ (or $\mathbb{R}$):

$$
\|v\|\ge 0,\ \|v\|=0\iff v=0;\quad \|\alpha v\|=|\alpha|\,\|v\|;\quad \|v+w\|\le \|v\|+\|w\|.
$$

- **How it is used (method flow):**
- **Input:** Vector space $V$, candidate size function.
- **Steps:** Check positivity, homogeneity, triangle inequality.
- **Output:** A normed vector space $(V,\|\cdot\|)$, enabling distance $d(v,w)=\|v-w\|$ and later completeness/continuity notions.
- **Why it is Core:** Centrality, high reusability, implementability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 2) Convergence in Normed Spaces via $\epsilon$-$N$ (Definition)

- **Type:** Definition (topology induced by a norm)
- **Localization:** Part 1, Section 5 Convergence, *Definition 2.1.5*
- **What it solves / Intuition:** Turns approaching a limit into a metric notion using $\|v-v_k\|$. This is the bridge from algebraic structure (vector space) to analytic reasoning (limits).
- **Mathematical form:** $v_k\to v$ iff $\|v-v_k\|\to 0$, equivalently:

$$
\forall \epsilon>0\ \exists N\ \forall k\ge N:\ \|v-v_k\|\le \epsilon.
$$

- **How it is used (method flow):**
- **Input:** Sequence $(v_k)$ in $V$, candidate limit $v$.
- **Steps:** Prove $\|v-v_k\|$ can be made arbitrarily small.
- **Output:** A convergence claim usable for continuity, series, and completeness arguments.
- **Why it is Core:** Centrality, implementability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, N, Y (4/5).

### 3) Reverse Triangle Inequality (Lemma)

- **Type:** Lemma (derived tool)
- **Localization:** Part 1, Section 4, *Lemma 2.1.2*
- **What it solves / Intuition:** Provides a lower bound on $\|v-w\|$ in terms of norm magnitudes, often used to prove uniqueness of limits and stability estimates.
- **Mathematical form:**

$$
\|v-w\|\ge \big|\,\|v\|-\|w\|\,\big|.
$$

- **How it is used (method flow):**
- **Input:** Two vectors or two candidate limits.
- **Steps:** Apply triangle inequality to $v=(v-w)+w$ (and the symmetric case).
- **Output:** A bound controlling norm differences by distances.
- **Why it is Core:** High reusability, implementability, appears as a key derived fact.
- **Core-ness check (Q1–Q5):** Y, Y, Y, N, Y (4/5).

### 4) Cauchy Sequences (Definition) and the No-Need-to-Guess-the-Limit Trick

- **Type:** Definition + proof strategy
- **Localization:** Banach Space (Part 1), Section 3, *Definition 3.1.1* and the surrounding discussion (problem with convergence definition)
- **What it solves / Intuition:** Convergence requires knowing the limit $v$; Cauchy-ness avoids that by only comparing pairs $v_k,v_l$. It is the standard way to prove existence of limits once completeness is available.
- **Mathematical form:**

$$
(v_k)\ \text{is Cauchy}\ \iff\ \forall\epsilon>0\ \exists N\ \forall k,l\ge N:\ \|v_k-v_l\|\le\epsilon.
$$

- **How it is used (method flow):**
- **Input:** A sequence defined implicitly (e.g., by partial sums/iterates) where the limit is not obvious.
- **Steps:** Prove pairwise distances shrink; then invoke completeness (Banach/Hilbert) to conclude convergence.
- **Output:** Existence of a limit element in the space without constructing it explicitly.
- **Why it is Core:** Centrality, implementability, high reusability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 5) Completeness and Banach Spaces (Definition)

- **Type:** Definition (completeness axiom)
- **Localization:** Banach Space (Part 1), Section 4, *Definition 3.1.4*; plus proof example *Theorem 3.1.6* ($C([a,b])$ is Banach)
- **What it solves / Intuition:** Completeness guarantees that internally convergent behavior (Cauchy) actually converges to an element *within the same space*. This makes infinite processes (limits/series/iterative methods) well-posed.
- **Mathematical form:** A normed space $(V,\|\cdot\|)$ is Banach iff every Cauchy sequence in $V$ converges in $V$.
- **How it is used (method flow):**
- **Input:** A normed space and a Cauchy sequence.
- **Steps:** Use completeness to assert existence of $v\in V$ with $\|v-v_k\|\to 0$.
- **Output:** Guaranteed limits for approximations (e.g., uniform limits of functions, limits of $\ell^p$ sequences).
- **Why it is Core:** Centrality, high reusability, implementability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 6) Supremum and the Supremum (Infinity) Norm on $C([a,b])$

- **Type:** Definition + construction (norm built from an extremal value)
- **Localization:** Normed Vector Spaces Part 2, Section 1 (*Definition 1.5.1*), Section 4 (*Theorem 6.3*), Section 5 (definition of $C[a,b]$ and $\|\cdot\|_\infty$)
- **What it solves / Intuition:** The supremum formalizes least upper bound and enables the uniform (max) norm on continuous functions. On a closed bounded interval, continuity ensures the supremum is attained (so the max is finite), making $\|\cdot\|_\infty$ practical.
- **Mathematical form:** For $f\in C([a,b])$,

$$
\|f\|_\infty = \max_{x\in[a,b]} |f(x)|.
$$

- **How it is used (method flow):**
- **Input:** Continuous function on $[a,b]$.
- **Steps:** Use $\max$ existence (Theorem 6.3) to define the norm; verify the three norm axioms.
- **Output:** A concrete Banach-space example supporting uniform convergence and function-operator analysis.
- **Why it is Core:** Centrality (builds a key example), implementability, high reusability.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 7) $\ell^p(\mathbb{N})$ Spaces and the Correct $p$-Norm; Minkowski as Triangle Inequality Engine

- **Type:** Definition + key inequality usage
- **Localization:** Banach Space (Part 1), Section 6 ($\ell^p$ definition and norm); Banach Space (Part 2), Section 1 (wrong norm attempt, correct $\|\cdot\|_p$); *Theorem 3.2.3* mentions Minkowski (*book Theorem 1.7.3*)
- **What it solves / Intuition:** $\ell^p$ is a canonical infinite-dimensional space for sequences. The notes emphasize a common pitfall: $\sum |x_k|^p$ is not a norm for $p\ne 1$; the $p$-th root fixes homogeneity. Minkowski inequality is the core tool that makes the triangle inequality hold.
- **Mathematical form:**

$$
\ell^p = \left\{x=(x_k): \sum_{k=1}^{\infty} |x_k|^p < \infty\right\},\qquad
\|x\|_p = \left(\sum_{k=1}^{\infty} |x_k|^p\right)^{1/p}.
$$

(Minkowski, used as triangle inequality)

$$
\|x+y\|_p\le \|x\|_p+\|y\|_p.
$$

- **How it is used (method flow):**
- **Input:** A sequence model $x$ and exponent $p\ge 1$.
- **Steps:** Define $\|\cdot\|_p$; rely on Minkowski to justify the triangle inequality; then leverage completeness result to conclude Banach.
- **Output:** A standard Banach space enabling operator examples (shift/sum) and Hilbert specialization at $p=2$.
- **Why it is Core:** Centrality, high reusability, implementability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 8) Bounded Linear Maps and Operator Norm (Definition + verification workflow)

- **Type:** Definition + implementation workflow (well-defined → linear → bounded)
- **Localization:** Banach Space (Part 2), Section 2 Linear Maps, *Definition 2.4.1* (boundedness) and operator norm; Section 3 examples (multiplication operator on $C[0,2]$, shift-sum operator on $\ell^p$)
- **What it solves / Intuition:** In infinite-dimensional settings, linearity alone is insufficient; boundedness controls growth and aligns with continuity. The operator norm provides a quantitative bound and a uniform way to compare operators.
- **Mathematical form:** $T:V\to V$ bounded if $\exists k\ge 0$ such that

$$
\|Tv\|\le k\|v\|\ \forall v\in V,\qquad \|T\| := \inf\{k: \|Tv\|\le k\|v\|\ \forall v\}.
$$

- **How it is used (method flow):**

`lang
Given a linear rule T and a normed space (V, ||·||):
1) Well-definedness: show Tv ∈ V for all v ∈ V (finiteness / closure).
2) Linearity: verify T(αv+βw)=αTv+βTw.
3) Boundedness: derive ||Tv|| ≤ k||v||; report k as an operator-norm bound.
`

- **Why it is Core:** Centrality (bridges analysis and operator theory), high reusability, implementability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 9) Inner Product on Complex Vector Spaces; Conjugate Linearity (Definition)

- **Type:** Definition (additional structure beyond a norm)
- **Localization:** Hilbert Space (Part 1), Section 2, *Definition 4.1.1*; Section 4 discusses conjugate linearity in the second argument
- **What it solves / Intuition:** The inner product encodes angles/orthogonality and enables projection-like reasoning. In complex spaces, the second-slot behavior is conjugate-linear, which is essential for consistent positivity.
- **Mathematical form:** $\langle\cdot,\cdot\rangle:V\times V\to\mathbb{C}$ with linearity in the first argument, conjugate symmetry $\langle v,w\rangle=\overline{\langle w,v\rangle}$, and positive definiteness $\langle v,v\rangle\ge 0$, equality only at $v=0$.
- **How it is used (method flow):**
- **Input:** A candidate bilinear-like form.
- **Steps:** Check the three axioms; use conjugate symmetry to derive conjugate linearity in the second argument.
- **Output:** An inner product space supporting induced norms, Cauchy–Schwarz, and Hilbert-space completeness.
- **Why it is Core:** Centrality, high reusability, implementability.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 10) Inner Product Induces a Norm + Cauchy–Schwarz + Parallelogram/POLARIZATION (Toolchain)

- **Type:** Theorem + key inequalities/identities
- **Localization:** Hilbert Space (Part 1), Section 5 (*Theorem/Lemma 4.1.3*); Section 6 lists Cauchy–Schwarz and Parallelogram law (Theorem 4.1.4 referenced)
- **What it solves / Intuition:** This toolchain connects geometry to analysis:
- $\|v\|=\sqrt{\langle v,v\rangle}$ makes every inner product space a normed space.
- Cauchy–Schwarz bounds correlations and powers many convergence/boundedness proofs.
- Parallelogram law characterizes when a norm comes from an inner product; polarization reconstructs the inner product from the norm.
- **Mathematical form:**

$$
\|v\| := \sqrt{\langle v,v\rangle},\qquad |
\langle v,w\rangle|\le \|v\|\,\|w\|.
$$

$$
\|v+w\|^2+\|v-w\|^2 = 2(\|v\|^2+\|w\|^2).
$$

- **How it is used (method flow):**
- **Input:** Inner product (or just a norm suspected to come from one).
- **Steps:** Define $\|\cdot\|$; apply Cauchy–Schwarz to prove triangle inequality and boundedness of functionals; use parallelogram/polarization for characterization and reconstruction.
- **Output:** A consistent analytic framework for Hilbert spaces.
- **Why it is Core:** Centrality, high reusability, implementability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 11) Hilbert Spaces (Definition) and $\ell^2$ as the Canonical Example

- **Type:** Definition + canonical construction
- **Localization:** Hilbert Space (Part 2), Section 1 (*Definition 4.1.5*); Section 2 (*Theorem 4.2.1*) and its well-definedness proof via Cauchy–Schwarz/Hölder
- **What it solves / Intuition:** A Hilbert space is a Banach space whose norm comes from an inner product. This structure supports orthogonality, expansions, and (later) representation theorems.
- **Mathematical form:** Hilbert space $\mathcal{H}$ = complete inner product space; for $\ell^2$:

$$
\langle x,y\rangle = \sum_{k=1}^{\infty} x_k\overline{y_k},\qquad \|x\|_2 = \left(\sum_{k=1}^{\infty} |x_k|^2\right)^{1/2}.
$$

- **How it is used (method flow):**
- **Input:** Candidate space (e.g., sequences) and inner product formula.
- **Steps:** Prove the inner product is well-defined (absolute convergence via Cauchy–Schwarz/Hölder); inherit norm; invoke completeness.
- **Output:** A working Hilbert space instance ($\ell^2$) used for functional/operator examples.
- **Why it is Core:** Centrality, high reusability, implementability, high frequency.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 12) Bounded Linear Functionals on Hilbert Spaces + Series-Defined Functional Pattern

- **Type:** Operator/algorithmic pattern (define → prove well-defined → bound)
- **Localization:** Hilbert Space (Part 2), Section 3 Operators: boundedness definition; Example 3 ($\Phi v=\langle v,w\rangle$); Example 4 (series-defined $\Phi$ with weights $1/k^2$)
- **What it solves / Intuition:** Linear functionals $\Phi:\mathcal{H}\to\mathbb{C}$ are measurements of vectors. Boundedness $|\Phi v|\le K\|v\|$ is the analytic condition that makes them continuous and well-behaved. The notes give a reusable pattern for functionals defined by infinite series: show absolute convergence using Cauchy–Schwarz and a convergent weight series.
- **Mathematical form:**

$$
|\Phi v|\le K\|v\|_{\mathcal{H}}.
$$

Example pattern (weights $a_k$, unit vectors $v_k$):

$$
\Phi v = \sum_{k=1}^{\infty} a_k\,\langle v,v_k\rangle,\qquad |\langle v,v_k\rangle|\le \|v\|\,\|v_k\|.
$$

- **How it is used (method flow):**
- **Input:** Proposed functional definition.
- **Steps:** Bound term magnitudes using Cauchy–Schwarz; compare to $\sum |a_k|$ or $\sum |a_k|^2$; conclude convergence and a global constant $K$.
- **Output:** A verified bounded linear functional with an explicit bound.
- **Why it is Core:** Centrality (leads directly to Riesz), high reusability, implementability.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

### 13) Riesz Representation Theorem (Hilbert-space dual identification)

- **Type:** Theorem (representation/duality)
- **Localization:** Hilbert Space (Part 2), Section 4, *Theorem 4.4.3 (preview)*
- **What it solves / Intuition:** Classifies all bounded linear functionals on a Hilbert space: every such functional is an inner product with a unique vector. This converts abstract functionals into concrete vectors and underpins many algorithms (projection, least squares) in Hilbert settings.
- **Mathematical form:** For bounded linear $\Phi$ on $\mathcal{H}$, $\exists!\,w\in\mathcal{H}$ such that

$$
\Phi(v)=\langle v,w\rangle\quad \forall v\in\mathcal{H}.
$$

- **How it is used (method flow):**
- **Input:** A bounded linear functional $\Phi$.
- **Steps:** Invoke Riesz to obtain the representing vector $w$ (unique); rewrite $\Phi$ evaluations as inner products.
- **Output:** A concrete representation enabling bounds $\|\Phi\|=\|w\|$ and constructive reasoning.
- **Why it is Core:** Centrality, novelty (major theorem in this flow), high reusability, implementability.
- **Core-ness check (Q1–Q5):** Y, Y, Y, Y, Y (5/5).

## Dependency Graph (text)

- Norm (Def 2.1.1) → Convergence (Def 2.1.5) → Cauchy (Def 3.1.1) → Completeness/Banach (Def 3.1.4)
- Supremum (Def 1.5.1) + Max-attainment on $[a,b]$ (Thm 6.3) → Supremum norm on $C([a,b])$ → Banach example (Thm 3.1.6)
- $\ell^p$ definition → correct $\|\cdot\|_p$ → Minkowski → $\ell^p$ is Banach (Thm 3.2.3)
- Inner product (Def 4.1.1) → induced norm (Thm 4.1.3) + Cauchy–Schwarz → Hilbert (Def 4.1.5)
- Hilbert + bounded functional definition → functional examples → Riesz representation (Thm 4.4.3)

## Prerequisites (Optional)

- Basic linear algebra: vector spaces, linear combinations, matrix intuition.
- Basic real analysis: limits in $\mathbb{R}$, sup/inf, continuity on compact sets (Weierstrass theorem; used as Theorem 6.3).
- Inequalities (used but not fully proven in the notes):
- Minkowski inequality (for $\ell^p$ triangle inequality; cited as book Theorem 1.7.3).
- Hölder inequality (mentioned alongside Cauchy–Schwarz in the $\ell^2$ inner product well-definedness proof).
- Series basics: geometric series convergence (used in the $\|\cdot\|_\infty$ convergence example) and convergence of $\sum 1/k^2$ (used in the series-defined functional example).

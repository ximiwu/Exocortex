## Paper Info

- Title: 01325 Mathematics 4 (Real Analysis): Normed Vector Spaces, Banach Spaces, Hilbert Spaces (course notes)
- Authors: Ole Christensen (lecturer; DTU) — explicitly named in the Hilbert space part
- Year: Not specified in the provided notes
- Keywords (graphics/math): Functional analysis; normed spaces; convergence; Cauchy sequences; completeness; Banach spaces; Hilbert spaces; operator theory; bounded linear maps; operator norm; $\ell^p$ and $L^p$ spaces; $C([a,b])$ and supremum norm; Cauchy–Schwarz; Minkowski inequality; Riesz representation (preview); Fourier transform; wavelets; B-splines; signal processing; quantum mechanics

## Background

### Research Object

- Build an abstract framework for “vectors” that are not necessarily finite-dimensional coordinates, but can be functions (signals) or infinite sequences.
- Equip these spaces with quantitative notions of “size” and “closeness” (norms / inner products) so that limits, stability, and operator behavior can be discussed rigorously.
- Source localization: “Normed vector spaces, Part I”, §3 (norm motivation/definition); “Hilbert spaces, Part I”, §2–§5 (inner products induce norms).

### Application Scenarios

- Signal processing: treat a time-domain signal as a function $f(t)$ and analyze its frequency content via the Fourier transform.
- Source localization: “Normed vector spaces, Part I”, §2 (signal example; Fourier transform motivation).
- Example formula (as used in the notes):

$$
\hat{f}(\gamma) = \int_{-\infty}^{\infty} f(x) e^{-2\pi i x \gamma}\,dx
$$

- Physics (quantum mechanics): represent physical states via wavefunctions $\Psi(r,t)$ with finite $\int_{\mathbb{R}^3}|\Psi(r,t)|^2\,dr$, motivating Hilbert spaces (e.g., $L^2$).
- Source localization: “Hilbert spaces, Part I”, §5 (classical vs quantum; $L^2(\mathbb{R}^3)$; observables as operators).

### Lineage / Prior Methods Being Generalized

- Generalize Euclidean geometry in $\mathbb{R}^n$ / $\mathbb{C}^n$ to infinite-dimensional settings:
- Function spaces such as $C([a,b])$ with $\|\cdot\|_\infty$ (built on the “continuous function attains its supremum on $[a,b]$” theorem).
- Source localization: “Supremum → $C[a,b]$ and $\|\cdot\|_\infty$”, §4–§6 (Theorem 6.3; definition/verification of sup norm).
- Sequence spaces $\ell^p(\mathbb{N})$ with $p$-norms and completeness properties (Banach spaces).
- Source localization: “Banach spaces, Part I”, §6; “Banach spaces, Part II”, §1–§3 ($\ell^p$, correct $p$-norm, Minkowski discussion).

## Pain Points

### Proof/Reasoning Gap (Learning Pain Point)

- A computation-first calculus background does not prepare students to justify why definitions and theorems work; the notes emphasize a shift to rigorous proofs and derivations.
- Source localization: “Normed vector spaces, Part I”, §1 (course framing: compute vs prove).

### “Functions as Vectors” Needs Structure

- Treating signals or wavefunctions as “just functions” is too vague: transforms/integrals (Fourier) or probabilistic interpretations (quantum) require explicit membership in spaces like $L^1$ or $L^2$ to be well-defined and numerically stable.
- Source localization: “Normed vector spaces, Part I”, §2 (Fourier transform requires integrability); “Hilbert spaces, Part I”, §5 ($L^2$ condition for wavefunctions).

### Convergence Without a Norm Is Not Actionable

- Without a norm/metric, there is no principled way to define convergence of function/sequence approximations, so discussions of approximation quality or stability become informal.
- Source localization: “Normed vector spaces, Part I”, §3–§5 (norm; convergence ideas); “Banach spaces, Part I”, §2–§4 (Cauchy vs convergence; completeness).

### Infinite-Dimensional Operator Pathologies

- In finite dimensions, linearity often suffices (all operators behave “nicely” and are representable by matrices), but in infinite dimensions an extra control condition is needed: boundedness (captured via $\|Tv\|\le k\|v\|$).
- Source localization: “Banach spaces, Part II”, §2–§3 (bounded linear maps; operator norm; examples).
- Physics adds another complication: many important operators are unbounded; the notes explicitly flag this as outside the typical “bounded-operator” classroom comfort zone.
- Source localization: “Hilbert spaces, Part I”, §5 (unbounded operators remark).

## What This Paper Solves (Verifiable Problem Statement)

- Input: a vector space $V$ (often of functions or sequences) over $\mathbb{R}$ or $\mathbb{C}$, plus candidate constructions for (a) a norm $\|\cdot\|$ or (b) an inner product $\langle\cdot,\cdot\rangle$, and linear maps $T$ / functionals $\Phi$ acting on $V$.
- Output: a rigorous “toolbox” that
1) validates $\|\cdot\|$ via norm axioms (positivity, homogeneity, triangle inequality),
2) defines convergence/Cauchy sequences using $\|\cdot\|$,
3) checks completeness (Banach/Hilbert property) for key spaces, and
4) controls operators using boundedness and operator norms.
- Success criteria: (i) axioms/inequalities are proved, (ii) representative spaces are shown complete (e.g., $C([a,b])$ with $\|\cdot\|_\infty$; $\ell^p$ with $\|\cdot\|_p$; $\ell^2$ as a Hilbert space), and (iii) example operators/functionals satisfy well-definedness, linearity, and boundedness with explicit constants.
- Source localization: Definition 2.1.1 (norm), Definition 3.1.4 (Banach), Definition 4.1.5 (Hilbert), Definition 2.4.1 (bounded linear map), Theorem 3.1.6 ($C([a,b])$ Banach), Theorem 4.2.1 ($\ell^2$ Hilbert), Theorem 4.4.3 (Riesz representation, preview).

## Core Contributions (1–5 items)

1) Defines norms and motivates why norms are needed beyond $\mathbb{R}^n$ (e.g., for function spaces underlying Fourier analysis). Important because it supplies a universal “size” notion to compare approximations; better than ad-hoc measures when moving to infinite dimensions.  
- Source localization: “Normed vector spaces, Part I”, §2–§3; Definition 2.1.1.

2) Establishes convergence/Cauchy-sequence machinery and introduces completeness via Banach spaces. Important because it replaces “guessing the limit” by “prove Cauchy ⇒ convergent” in complete spaces; stronger than working in non-complete settings where Cauchy sequences can “escape” the space.  
- Source localization: “Banach spaces, Part I”, §2–§5; Definition 3.1.4; Theorem 3.1.6.

3) Develops canonical infinite-dimensional examples $C([a,b])$ with $\|\cdot\|_\infty$ and $\ell^p(\mathbb{N})$ with $\|\cdot\|_p$, including why the naive “sum of $p$-powers” is not a norm (unless $p=1$). Important because these are the main working spaces in analysis and applications; better because the correct norm choice ensures the intended scaling and triangle inequality (via Minkowski).  
- Source localization: “Supremum → $C[a,b]$ and $\|\cdot\|_\infty$”, §4–§6; “Banach spaces, Part II”, §1–§3 (Minkowski reference).

4) Introduces bounded linear maps and the operator norm as the right notion of “stability” for operators on infinite-dimensional spaces, with worked examples (multiplication operator on $C[0,2]$; shift-sum on $\ell^p$). Important because boundedness provides uniform control and makes operator analysis tractable; better than “linearity only”, which is insufficient in infinite dimensions.  
- Source localization: “Banach spaces, Part II”, §2–§3; Definition 2.4.1.

5) Transitions to inner product spaces and Hilbert spaces, showing how inner products induce norms and enabling stronger geometric tools (Cauchy–Schwarz, parallelogram law, polarization identity). Important because Hilbert spaces underpin Fourier methods and quantum mechanics; better because inner products allow orthogonality/projection-style reasoning not available in general Banach spaces.  
- Source localization: “Hilbert spaces, Part I”, §2–§5; Lemma/Theorem 4.1.3; Definition 4.1.5; Theorem 4.2.1; Theorem 4.4.3 (preview).

## Assumptions & Limitations

- Field choice: many definitions are presented for complex vector spaces ($\mathbb{C}$), with the real case obtained by dropping complex conjugation in inner-product identities.
- Source localization: “Hilbert spaces, Part I”, §2–§4 (conjugate symmetry; conjugate linearity in the second slot).
- Some key inequalities/proofs are deferred or treated as known facts (e.g., Minkowski inequality for $\ell^p$; “uniform convergence preserves continuity” used in the $C([a,b])$ completeness proof).
- Source localization: “Banach spaces, Part II”, §1–§3; “Banach spaces, Part I”, Theorem 3.1.6 proof outline.
- Fourier transform and quantum-mechanics examples provide motivation, but the functional-analytic subtleties (e.g., extensions beyond $L^1$, distributions, domains of unbounded operators) are not developed here.
- Source localization: “Normed vector spaces, Part I”, §2; “Hilbert spaces, Part I”, §5.

## Connection to Graphics/Math

### Retrieval Tags

- Geometry: Norms, inner products, orthogonality
- Analysis: Convergence, Cauchy sequences, completeness
- Functional Analysis: Banach spaces, Hilbert spaces, $\ell^p$/$L^p$, $C([a,b])$
- Operator Theory: Bounded operators, operator norm, linear functionals, Riesz representation (preview)
- Harmonic / Time-Frequency Analysis: Fourier transform, wavelets (motivational roadmap)

### Quick Map (Application → Space/Tool → Why It Matters)

| Application / Object | Mathematical Space / Tool | Why this abstraction is needed | Source localization |
|---|---|---|---|
| Time signals $f(t)$ | $L^1(\mathbb{R})$ (integrability), Fourier transform | Ensures the transform integral is meaningful; enables frequency-domain interpretation | “Normed vector spaces, Part I”, §2 |
| Continuous functions on $[a,b]$ | $C([a,b])$, $\|\cdot\|_\infty$ | Uniform error control; supports completeness (Banach) for limit arguments | Theorem 6.3; Theorem 3.1.6 |
| Infinite sequences | $\ell^p(\mathbb{N})$, $\|\cdot\|_p$ | Canonical discrete analogs of $L^p$; stable operator estimates via Minkowski/Hölder | “Banach spaces, Part I/II”, $\ell^p$ sections |
| Quantum states $\Psi(r,t)$ | $L^2(\mathbb{R}^3)$, Hilbert space structure | Probability interpretation + geometry (projections/orthogonality) | “Hilbert spaces, Part I”, §5 |
| Observables / functionals | Bounded operators/functionals; Riesz (preview) | Converts “measurements” into operator/functional questions with norm control | “Hilbert spaces, Part I”, §3–§4 |

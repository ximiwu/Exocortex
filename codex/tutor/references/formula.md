# Formula Cheat Sheet (Developer-Ready)

Source: `input/input.md`

## Extraction scope

- This extractor targets only equations explicitly marked with LaTeX `\tag{...}`.
- Searched `input/input.md` (and `input/`) for `\tag` / `tag` and found **zero** matches.
- The section **Tagged Equations** is therefore empty; **Fallback Equations** captures the main *untagged* formulas present in the document so you still get an implementable reference.

## Global notation (grounding)

| Notation | Type | Meaning in the notes | Implementation mapping |
|---|---|---|---|
| $V$ | set / type | vector space (often normed / inner-product space) | pick a concrete representation: `float[]`, `complex[]`, sparse vector, function samples |
| $v,w$ | element | vectors in $V$ | arrays/tensors; for functions use sampled arrays on a grid |
| $\alpha,\beta$ | scalar | real/complex scalars | `float` / `complex` |
| $\|\cdot\|$ | function | norm $V\to\mathbb{R}_{\ge 0}$ | `norm(v)` used for distances, error, stopping criteria |
| $\langle \cdot,\cdot\rangle$ | function | inner product (Hermitian for complex spaces) | `inner(v,w)`; for complex vectors use conjugate on the 2nd argument (e.g. `vdot`) |
| $L^p(\Omega)$ | space | $p$-integrable functions on domain $\Omega$ | discretize integral by quadrature / sums over grid |
| $\ell^p(\mathbb{N})$ | space | $p$-summable sequences | finite arrays approximate truncated sequences |
| $f(t), f(x)$ | function | signal / function | sampled signal `f[n]` with sampling period `dt` |
| $\hat f(\gamma)$ | function | Fourier transform of $f$ | FFT-based spectrum `F[k]`, with frequency bin mapping |
| $\Psi(r,t)$ | function | quantum wavefunction | 3D complex grid + normalization via discrete integral |
| $A$ | operator / matrix | linear operator (observable) | dense/sparse matrix; apply as `A @ psi` |
| $(\lambda_n,\psi_n)$ | pair | eigenvalue / eigenvector | use eigensolvers; normalize eigenvectors by chosen norm |
| $\Phi$ | functional | bounded linear functional on a Hilbert space | implement as `phi(v)`, often via an inner product with a fixed vector |

## Tagged equations (`\tag{...}`)

No tagged equations exist in `input/input.md`.

## Fallback equations (untagged, but central)

### Fourier transform (continuous definition)

$$
\hat{f}(\gamma) = \int_{-\infty}^{\infty} f(x)\,e^{-2\pi i x \gamma}\,dx
$$

- Algorithmic role: maps a time/space-domain signal to its frequency representation (feature extraction, filtering, spectrum analysis).
- Implementation notes: in code you almost always use the discrete FFT on samples $f[n]$; keep track of sampling interval and frequency bins (scaling conventions differ).

### Integrability condition for $L^1(\mathbb{R})$ (Fourier-transform existence in the notes)

$$
\int_{-\infty}^{\infty} |f(x)|\,dx < \infty
$$

- Algorithmic role: precondition (“input is absolutely integrable”) to justify applying the Fourier transform.
- Implementation notes: discretize as `sum(abs(f[n])) * dt` and treat it as a diagnostic/assumption check rather than a hard guarantee.

### Euclidean $\ell^2$ norm on $\mathbb{R}^n/\mathbb{C}^n$

$$
\|x\|_2 = \sqrt{\sum_{k=1}^{n} |x_k|^2}
$$

- Algorithmic role: default length/error metric; used for distances and thresholds.
- Implementation notes: prefer numerically stable implementations (`hypot`/BLAS norms) to reduce overflow/underflow for large vectors.

### Square-integrability condition for $L^2$ (“finite energy”)

$$
\int_{-\pi}^{\pi} |f(x)|^2\,dx < \infty
$$

- Algorithmic role: membership test for energy-bounded signals; justifies inner-product/Hilbert-space machinery.
- Implementation notes: discretize as `sum(abs(f[n])**2) * dx`; if you later normalize, divide by $\sqrt{\int |f|^2}$.

### Norm axioms (what your `norm()` must satisfy)

1. Positivity:

$$
\|v\| \ge 0,\quad \forall v\in V
$$

2. Homogeneity:

$$
\|\alpha v\| = |\alpha|\,\|v\|,\quad \forall v\in V
$$

3. Triangle inequality:

$$
\|v+w\| \le \|v\|+\|w\|,\quad \forall v,w\in V
$$

- Algorithmic role: contract for any “distance-like” quantity used in convergence checks, bounds, and proofs.
- Implementation notes: when you implement a custom norm (e.g., weighted, Sobolev-like), unit-test these properties on random inputs.

### Reverse triangle inequality (useful bound)

$$
\|v-w\| \ge \big|\|v\|-\|w\|\big|
$$

- Algorithmic role: bounds how much a norm can change when the input changes; supports stability/error estimates.
- Implementation notes: often used as `abs(norm(v) - norm(w)) <= norm(v - w)` in code assertions/tests.

### Convergence in a normed space (iterative stopping criterion)

$$
\|v-v_k\| \to 0 \quad (k\to\infty)
$$

Equivalent $\varepsilon$-criterion:

$$
\forall \varepsilon>0\,\exists N\in\mathbb{N}\ \text{s.t.}\ k\ge N \Rightarrow \|v-v_k\|\le \varepsilon
$$

- Algorithmic role: formalizes “iterate until close enough”; maps directly to `if norm(v - v_k) <= eps: stop`.
- Implementation notes: if $v$ is unknown (common in practice), replace with residual norms (e.g., `norm(r_k)`).

### Norm induced by an inner product

$$
\|v\| := \sqrt{\langle v, v \rangle}
$$

- Algorithmic role: defines a consistent norm from your `inner(v,v)`; typical for optimization and projection methods.
- Implementation notes: for complex vectors use the Hermitian inner product so $\langle v,v\rangle\in\mathbb{R}_{\ge 0}$.

### Cauchy–Schwarz inequality (core bound)

$$
|\langle v, w \rangle| \le \|v\|\,\|w\|
$$

- Algorithmic role: upper-bounds correlations/dot products; used to prove triangle inequality and to bound errors.
- Implementation notes: numerically, this also motivates normalizing vectors before computing similarity scores.

### $\ell^2(\mathbb{N})$ inner product (infinite sequences)

$$
\langle x, y \rangle := \sum_{k=1}^{\infty} x_k\,\overline{y_k}
$$

- Algorithmic role: defines the geometry for sequences; the prototype for many function-space discretizations.
- Implementation notes: in code you truncate to $k=1\ldots K$; use conjugation on $y_k$ for complex data.

### Linear functional as an inner product with a fixed vector

$$
\Phi v := \langle v, w \rangle
$$

- Algorithmic role: represent “measurements” or linear queries as a dot/inner product; turns $\Phi$ into a reusable operator.
- Implementation notes: store $w$ and implement `phi(v) = inner(v, w)`; Cauchy–Schwarz gives a Lipschitz bound `abs(phi(v)) <= norm(w) * norm(v)`.

### Quantum-mechanics square-integrability (normalizability)

$$
\int_{\mathbb{R}^3} |\Psi(r, t)|^2\,dr < \infty
$$

- Algorithmic role: precondition for interpreting $|\Psi|^2$ as a probability density; enables normalization.
- Implementation notes: on a 3D grid with spacing $\Delta x\Delta y\Delta z$, approximate with `sum(abs(Psi)**2) * dV`; normalize by dividing $\Psi$ by the square root of that value.

### Eigenvalue equation (observables / modes)

$$
A\psi_n = \lambda_n \psi_n
$$

- Algorithmic role: compute modes/steady states; in physics, eigenvalues are measurable outcomes.
- Implementation notes: use `eig`/`eigs` depending on size/sparsity; choose normalization ($\|\psi_n\|=1$) consistent with your inner product.

第 3 段：面积为什么不是简单乘 $J$

面积变换比体积更微妙，因为面积元带有方向信息，即法向。

文中设参考面积元为

$$d\mathbf{S}=\mathbf{N}\,dS,$$

当前面积元为

$$d\mathbf{s}=\mathbf{n}\,ds.$$

再用一个额外的小向量 $d\mathbf{L}$ 组成小体积，利用

$$dV=d\mathbf{S}\cdot d\mathbf{L}, \qquad dv=d\mathbf{s}\cdot d\mathbf{l}, \qquad d\mathbf{l}=\mathbf{F}d\mathbf{L},$$

最终推出

$$d\mathbf{s}=J\mathbf{F}^{-T}d\mathbf{S},$$

也就是

$$\mathbf{n}\,ds=J\mathbf{F}^{-T}\mathbf{N}\,dS.$$

这条关系通常叫 Nanson 公式。

# 历史对话：


## 提问：

$$dV=d\mathbf{S}\cdot d\mathbf{L}, \qquad dv=d\mathbf{s}\cdot d\mathbf{l}, \qquad d\mathbf{l}=\mathbf{F}d\mathbf{L},$$最终推出$$d\mathbf{s}=J\mathbf{F}^{-T}d\mathbf{S},$$详细的推导过程？

## 回答：

可以。关键点是：**面积矢量不是普通向量**，它代表“有方向的面积元”，本质上和一个小体积的底面有关，所以它的变换不是直接乘 $\mathbf F$，也不是简单乘 $J$。

下面按你给出的思路推。

---

## 1. 参考构形与当前构形的小体积

参考构形里取一个面积矢量

$$
d\mathbf S=\mathbf N\,dS,
$$

再取一条小线元 $d\mathbf L$，它不必与面垂直。则这个小“斜柱体”的体积可写成

$$
dV=d\mathbf S\cdot d\mathbf L.
$$

变形后，对应的面积矢量和线元分别为

$$
d\mathbf s=\mathbf n\,ds,\qquad d\mathbf l=\mathbf F\,d\mathbf L,
$$

于是当前体积为

$$
dv=d\mathbf s\cdot d\mathbf l.
$$

另一方面，体积按 Jacobian 变换：

$$
dv=J\,dV.
$$

代入 $dV=d\mathbf S\cdot d\mathbf L$，得到

$$
dv=J(d\mathbf S\cdot d\mathbf L).
$$

---

## 2. 用两种方式表示同一个 $dv$

一方面，

$$
dv=d\mathbf s\cdot d\mathbf l
=d\mathbf s\cdot (\mathbf F\,d\mathbf L).
$$

把点积改写一下：

$$
d\mathbf s\cdot (\mathbf F\,d\mathbf L)
=
(\mathbf F^T d\mathbf s)\cdot d\mathbf L.
$$

所以

$$
dv=(\mathbf F^T d\mathbf s)\cdot d\mathbf L.
$$

另一方面，

$$
dv=J(d\mathbf S\cdot d\mathbf L)
=(J\,d\mathbf S)\cdot d\mathbf L.
$$

因此对任意 $d\mathbf L$，都有

$$
(\mathbf F^T d\mathbf s)\cdot d\mathbf L
=
(J\,d\mathbf S)\cdot d\mathbf L.
$$

由于这对**任意** $d\mathbf L$ 都成立，只能说明向量本身相等：

$$
\mathbf F^T d\mathbf s = J\,d\mathbf S.
$$

左乘 $\mathbf F^{-T}$，得到

$$
d\mathbf s = J\,\mathbf F^{-T}d\mathbf S.
$$

这就是 **Nanson 公式**：

$$
\boxed{d\mathbf s = J\,\mathbf F^{-T}d\mathbf S.}
$$

写成法向和面积的形式就是

$$
\boxed{\mathbf n\,ds = J\,\mathbf F^{-T}\mathbf N\,dS.}
$$

---

## 3. 为什么这里出现的是 $\mathbf F^{-T}$ 而不是 $\mathbf F$

因为面积元携带的是**法向信息**。  
线元的变换是

$$
d\mathbf l=\mathbf F\,d\mathbf L,
$$

但法向必须满足“与切向正交”的几何关系。正交关系在变换下会把 $\mathbf F$ 变成其逆转置 $\mathbf F^{-T}$。再乘上体积缩放 $J$，就得到面积矢量的变换律：

$$
d\mathbf s \sim J\mathbf F^{-T}d\mathbf S.
$$

所以：

- 长度元：看 $\mathbf F$

- 体积元：看 $J=\det\mathbf F$

- 面积矢量：看 $J\mathbf F^{-T}$

---

## 4. 也可以这样理解

如果只关心面积大小，不看方向，那么由

$$
\mathbf n\,ds = J\mathbf F^{-T}\mathbf N\,dS
$$

取模长可得

$$
ds = J\,\bigl|\mathbf F^{-T}\mathbf N\bigr|\,dS.
$$

这说明面积变化不仅依赖 $J$，还依赖原来这个面朝哪个方向（$\mathbf N$）。所以面积不是简单乘 $J$。

---

## 5. 一句话总结

Nanson 公式的推导核心就是把**同一个小体积**写成两种形式：

$$
dv=d\mathbf s\cdot (\mathbf F d\mathbf L)
\quad\text{和}\quad
dv=J(d\mathbf S\cdot d\mathbf L),
$$

再利用 $d\mathbf L$ 的任意性，推出

$$
\mathbf F^T d\mathbf s=Jd\mathbf S,
$$

从而得到

$$
\boxed{d\mathbf s=J\mathbf F^{-T}d\mathbf S.}
$$

如果你愿意，我也可以继续给你补一个“用两个切向量叉乘”推导 Nanson 公式的版本，那个更直观。
第 4 段：链式法则为什么会产生额外项

关键一步是对

$$\mathbf{V}(\mathbf{X},t)=\mathbf{v}(\phi(\mathbf{X},t),t)$$

在固定 $\mathbf{X}$ 下对时间求导。链式法则给出：

$$\mathbf{A}(\mathbf{X},t) = \frac{\partial \mathbf{v}}{\partial t}(\phi(\mathbf{X},t),t) + \frac{\partial \mathbf{v}}{\partial \mathbf{x}}(\phi(\mathbf{X},t),t)\, \frac{\partial \phi}{\partial t}(\mathbf{X},t)$$

更标准地写是

$$\mathbf{A}(\mathbf{X},t) = \frac{\partial \mathbf{v}}{\partial t}(\phi(\mathbf{X},t),t) + \nabla_{\mathbf{x}}\mathbf{v}(\phi(\mathbf{X},t),t)\,\frac{\partial \phi}{\partial t}(\mathbf{X},t).$$

又因为

$$\frac{\partial \phi}{\partial t}=\mathbf{V}=\mathbf{v}\circ\phi,$$

所以推前到欧拉空间后得到

$$\mathbf{a}(\mathbf{x},t) = \frac{\partial \mathbf{v}}{\partial t}(\mathbf{x},t) + (\mathbf{v}\cdot \nabla)\mathbf{v}(\mathbf{x},t).$$

其中第二项叫对流项或输运项。

第 5 段：为什么 $\mathbf{a}\neq \partial \mathbf{v}/\partial t$

文中说这是一个“看起来不直观”的结果：

$$\mathbf{a}(\mathbf{x},t)\neq \frac{\partial \mathbf{v}}{\partial t}(\mathbf{x},t).$$

其实一点也不神秘。原因是：

$\partial \mathbf{v}/\partial t$ 是在固定空间位置看速度随时间如何变化。

$\mathbf{a}$ 是跟着某块材料走时，它亲身经历到的速度变化。

如果速度场在空间上不均匀，即使一个固定位置上的时间变化为零，材料点沿着流线移动时仍可能进入更快或更慢的区域，于是它仍然有加速度。

一个最经典的例子是稳态喷管流：
即使 $\partial \mathbf{v}/\partial t=0$，流体穿过逐渐收缩的区域时，速度仍然会沿路径增加，因此 $\mathbf{a}\neq 0$。

也可以用“桥上看河”的画面来记：桥上的观察者可能看到某点流速并不随时间变，但顺流漂下的叶子仍会因为进入更快的水区而加速。对流项记录的正是这部分“因为自己在移动而多看到的变化”。

# 历史对话：


## 提问：

为啥大A是由小v对t求导得到的？为啥不是大V对t求导

## 回答：

其实 `大A` 本来就是由 `大V` 对时间求导得到的。

定义上，在拉格朗日描述里：

$$
\mathbf V(\mathbf X,t)=\frac{\partial \phi}{\partial t}(\mathbf X,t)
$$

所以材料加速度就是

$$
\mathbf A(\mathbf X,t)=\frac{\partial \mathbf V}{\partial t}(\mathbf X,t).
$$

你看到后面写成对 `小v` 求导，不是换了定义，而是因为 `大V` 不是独立函数，它本身就是 `小v` 和运动映射 $\phi$ 复合出来的：

$$
\mathbf V(\mathbf X,t)=\mathbf v(\phi(\mathbf X,t),t).
$$

因此一旦对 $\mathbf V$ 求导，就必然要写成

$$
\mathbf A(\mathbf X,t)
=\frac{\partial}{\partial t}\mathbf V(\mathbf X,t)
=\frac{\partial}{\partial t}\big[\mathbf v(\phi(\mathbf X,t),t)\big].
$$

然后才对这个复合函数用链式法则，得到

$$
\mathbf A(\mathbf X,t)
=
\frac{\partial \mathbf v}{\partial t}(\phi(\mathbf X,t),t)
+
\nabla_{\mathbf x}\mathbf v(\phi(\mathbf X,t),t)\,
\frac{\partial \phi}{\partial t}(\mathbf X,t).
$$

所以逻辑顺序是：

1. 先定义

$$
\mathbf A=\frac{\partial \mathbf V}{\partial t}.
$$

2. 再利用

$$
\mathbf V=\mathbf v\circ \phi
$$

把它改写成对 `小v` 的求导。

也就是说，不是“为什么不用大V求导”，而是“对大V求导之后，展开时自然变成了对小v这个复合函数求导”。

你可以把它理解成：

- `大V(X,t)`：跟着材料点看速度

- `小v(x,t)`：在空间位置上定义的速度场

- `大A(X,t)`：跟着材料点看速度的时间导数，所以当然是

$$
\frac{\partial \mathbf V}{\partial t}
$$

- 但因为 $\mathbf V$ 由 $\mathbf v(\phi(\mathbf X,t),t)$ 给出，所以计算时必须对这个复合式求导，于是出现额外项

最后推到欧拉坐标，就变成

$$
\mathbf a(\mathbf x,t)
=
\frac{\partial \mathbf v}{\partial t}
+
(\mathbf v\cdot\nabla)\mathbf v.
$$

如果你愿意，我可以接着给你画一张“`大V/小v/phi/A/a` 五个量之间关系”的符号图，基本一眼就顺了。

## 提问：

然后所以推前到欧拉空间后得到$$\mathbf{a}(\mathbf{x},t) = \frac{\partial \mathbf{v}}{\partial t}(\mathbf{x},t) + (\mathbf{v}\cdot \nabla)\mathbf{v}(\mathbf{x},t).$$这一步的详细推导？

## 回答：

可以，关键就是把“拉格朗日量”重新写成“欧拉量”。

先从你已经有的式子开始：

$$
\mathbf A(\mathbf X,t)
=\frac{\partial \mathbf v}{\partial t}(\phi(\mathbf X,t),t)
+\nabla_{\mathbf x}\mathbf v(\phi(\mathbf X,t),t)\,
\frac{\partial \phi}{\partial t}(\mathbf X,t).
$$

现在分三步看。

**1. 先定义欧拉加速度 `a` 是 `A` 的推前**

欧拉描述里的加速度场定义为

$$
\mathbf a(\mathbf x,t):=\mathbf A(\phi^{-1}(\mathbf x,t),t).
$$

也就是：在时刻 $t$，占据位置 $\mathbf x$ 的那一个材料点，它的加速度是多少。

等价地说，如果

$$
\mathbf x=\phi(\mathbf X,t),
$$

那么

$$
\mathbf a(\mathbf x,t)=\mathbf A(\mathbf X,t).
$$

所以只要把上面 `A(X,t)` 里的 $\phi(\mathbf X,t)$ 换成 $\mathbf x$ 就行。

---

**2. 把每一项都改写成欧拉变量**

因为 $\mathbf x=\phi(\mathbf X,t)$，所以第一项直接变成

$$
\frac{\partial \mathbf v}{\partial t}(\phi(\mathbf X,t),t)
=
\frac{\partial \mathbf v}{\partial t}(\mathbf x,t).
$$

再看第二项。由速度定义，

$$
\frac{\partial \phi}{\partial t}(\mathbf X,t)=\mathbf V(\mathbf X,t)
=\mathbf v(\phi(\mathbf X,t),t)
=\mathbf v(\mathbf x,t).
$$

因此

$$
\nabla_{\mathbf x}\mathbf v(\phi(\mathbf X,t),t)\,
\frac{\partial \phi}{\partial t}(\mathbf X,t)
=
\nabla_{\mathbf x}\mathbf v(\mathbf x,t)\,\mathbf v(\mathbf x,t).
$$

于是得到

$$
\mathbf a(\mathbf x,t)
=
\frac{\partial \mathbf v}{\partial t}(\mathbf x,t)
+\nabla_{\mathbf x}\mathbf v(\mathbf x,t)\,\mathbf v(\mathbf x,t).
$$

---

**3. 为什么这就是 $(\mathbf v\cdot\nabla)\mathbf v$**

这是记号问题。设

$$
\mathbf v=(v_1,v_2,v_3).
$$

那么雅可比矩阵 $\nabla \mathbf v$ 作用在向量 $\mathbf v$ 上，分量写成

$$
\big(\nabla \mathbf v\,\mathbf v\big)_i
=
\sum_{j=1}^3 \frac{\partial v_i}{\partial x_j}v_j.
$$

而

$$
\big((\mathbf v\cdot\nabla)\mathbf v\big)_i
=
\sum_{j=1}^3 v_j\frac{\partial v_i}{\partial x_j}.
$$

这两个完全一样，所以

$$
\nabla \mathbf v\,\mathbf v=(\mathbf v\cdot\nabla)\mathbf v.
$$

因此最终

$$
\boxed{
\mathbf a(\mathbf x,t)
=
\frac{\partial \mathbf v}{\partial t}(\mathbf x,t)
+
(\mathbf v\cdot\nabla)\mathbf v(\mathbf x,t)
}
$$

---

如果你想，我还可以继续给你写一个“按指标记号一步一步展开”的版本，因为那个版本最不容易糊。

## 提问：

v和一个nabla点乘是什么意思

## 回答：

`(\mathbf v\cdot \nabla)` 不是先算出一个普通数，而是一个**微分算子**。

如果

$$
\mathbf v=(v_1,v_2,v_3),\qquad
\nabla=\left(\frac{\partial}{\partial x_1},\frac{\partial}{\partial x_2},\frac{\partial}{\partial x_3}\right),
$$

那么定义

$$
\mathbf v\cdot \nabla
=
v_1\frac{\partial}{\partial x_1}

+
v_2\frac{\partial}{\partial x_2}

+
v_3\frac{\partial}{\partial x_3}.
$$

所以它的意思是：

对某个量沿着速度方向做方向导数。

比如作用在一个标量场 $f(\mathbf x,t)$ 上：

$$
(\mathbf v\cdot\nabla)f
=
v_1\frac{\partial f}{\partial x_1}

+
v_2\frac{\partial f}{\partial x_2}

+
v_3\frac{\partial f}{\partial x_3}.
$$

如果作用在向量场 $\mathbf v$ 自己上，就是对每个分量分别作用：

$$
(\mathbf v\cdot\nabla)\mathbf v
=
\left(
v_1\frac{\partial v_1}{\partial x_1}+v_2\frac{\partial v_1}{\partial x_2}+v_3\frac{\partial v_1}{\partial x_3},
\;
v_1\frac{\partial v_2}{\partial x_1}+v_2\frac{\partial v_2}{\partial x_2}+v_3\frac{\partial v_2}{\partial x_3},
\;
v_1\frac{\partial v_3}{\partial x_1}+v_2\frac{\partial v_3}{\partial x_2}+v_3\frac{\partial v_3}{\partial x_3}
\right).
$$

更紧凑地写成分量形式：

$$
\big((\mathbf v\cdot\nabla)\mathbf v\big)_i
=
\sum_j v_j\frac{\partial v_i}{\partial x_j}.
$$

直观上，它表示：

流体微团虽然在固定点看起来速度场不变，但它自己往前走时，会“扫过”空间中不同位置的速度分布，因此产生额外变化。

所以

$$
\frac{D\mathbf v}{Dt}
=
\frac{\partial \mathbf v}{\partial t}

+
(\mathbf v\cdot\nabla)\mathbf v
$$

里的第二项，就是“因为自己在空间中移动而看到的变化”。

如果你愿意，我可以接着给你画一个“`v·∇` 为什么是方向导数”的二维小例子。
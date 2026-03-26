第 1 段：物质导数的定义与直觉

为了把上一节的结果写得更简洁，定义：

$$\frac{D}{Dt}\mathbf{v} = \frac{\partial \mathbf{v}}{\partial t} + (\mathbf{v}\cdot\nabla)\mathbf{v}.$$

于是

$$\mathbf{a}=\frac{D\mathbf{v}}{Dt}.$$

物质导数不是某种神秘新算子，它本质上就是：

$$\frac{D}{Dt}f(\mathbf{x},t) = \frac{d}{dt}f(\mathbf{x}(t),t), \qquad \text{其中 } \dot{\mathbf{x}}(t)=\mathbf{v}(\mathbf{x}(t),t).$$

也就是说，$\frac{D}{Dt}$ 表示沿材料轨迹求导。

第 2 段：对任意欧拉场 $f$ 的一般形式

对任意欧拉标量场 $f(\mathbf{x},t)$，有

$$\frac{Df}{Dt} = \frac{\partial f}{\partial t} + \mathbf{v}\cdot \nabla f.$$

如果 $f$ 是向量场或张量场，形式完全类似，只是梯度和乘法要按张量规则理解。

这里还有一句非常重要的话：
欧拉场的物质导数，是其拉回到参考域后在固定材料坐标下时间导数的推前。

这句话表面抽象，实际意义很大：
拉格朗日时间导数和欧拉物质导数，是同一个物理变化在两套坐标描述下的对应形式。

因此可以把物质导数统一理解成两部分之和：一部分是固定位置处的局部时间变化，另一部分是材料迁移到别处后，由空间非均匀性带来的额外变化。

第 3 段：形变梯度的演化方程

这段接着讨论 $\mathbf{F}$ 的欧拉化演化。若 $\mathbf{f}$ 是 $\mathbf{F}$ 的推前，则

$$\frac{D\mathbf{f}}{Dt}=(\nabla \mathbf{v})\mathbf{f}.$$

这是一个极其关键的公式。它说明：

局部速度梯度 $\nabla \mathbf{v}$ 驱动局部形变梯度的演化。

从分量上看：

$$\frac{D f_{ij}}{Dt}=\frac{\partial v_i}{\partial x_k}f_{kj}.$$

这意味着当前的局部变形状态，会被当前的速度梯度继续左乘推进。

从直觉上说，$\mathbf{v}$ 告诉你“点怎么移动”，而 $\nabla \mathbf{v}$ 告诉你“附近不同点移动得有多不一样”。只有这种空间差异存在，拉伸、压缩、剪切和旋转才会逐步积累；如果每个点速度都完全一样，那就只是整体平移。

从物理上，$\nabla \mathbf{v}$ 可以分解成：

$$\nabla \mathbf{v}=\mathbf{D}+\mathbf{W},$$

其中

$\mathbf{D}=\frac12(\nabla \mathbf{v}+(\nabla \mathbf{v})^T)$ 是对称部分，控制拉伸和剪切率；

$\mathbf{W}=\frac12(\nabla \mathbf{v}-(\nabla \mathbf{v})^T)$ 是反对称部分，控制局部旋转率。

所以这个方程也可以理解为：
局部材料元会在速度场的拉伸、剪切和旋转作用下不断更新其 $\mathbf{F}$。

# 历史对话：


## 提问：

$\frac{Df}{Dt} = \frac{\partial f}{\partial t} + \mathbf{v}\cdot \nabla f.$，为啥后面又变成$\frac{D\mathbf{f}}{Dt}=(\nabla \mathbf{v})\mathbf{f}.$了

## 回答：

不是“又变成”了，而是这两个式子说的是两件不同层次的事，而且对这个特殊的 $\mathbf f$ 它们是同时成立的：

1. 一般定义  
对任意欧拉场 $f(\mathbf x,t)$，物质导数都定义为

$$
\frac{Df}{Dt}=\frac{\partial f}{\partial t}+\mathbf v\cdot \nabla f.
$$

如果 $f$ 是张量场，也是逐分量这样算。

2. 特殊运动学方程  
后面的 $\mathbf f$ 不是“任意场”，而是“形变梯度 $\mathbf F$ 的推前”这个特殊张量场。  
它除了满足上面的通用定义，还额外满足一个运动学恒等式：

$$
\frac{D\mathbf f}{Dt}=(\nabla \mathbf v)\mathbf f.
$$

所以正确理解是：

$$
\boxed{\frac{\partial \mathbf f}{\partial t}+(\mathbf v\cdot\nabla)\mathbf f=(\nabla\mathbf v)\mathbf f}
$$

左边是“物质导数的通用展开”，右边是“这个特殊场 $\mathbf f$ 的具体演化规律”。

直观地说：

- $\frac{\partial \mathbf f}{\partial t}+(\mathbf v\cdot\nabla)\mathbf f$：表示沿材料点走时，$\mathbf f$ 怎么变。

- $(\nabla \mathbf v)\mathbf f$：说明这种变化的原因，正是局部速度梯度在驱动它。

如果你愿意，我可以继续把

$$
\frac{D\mathbf f}{Dt}=(\nabla \mathbf v)\mathbf f
$$

从 $\mathbf F=\frac{\partial \mathbf x}{\partial \mathbf X}$ 一步一步推出来。

## 提问：

推导

## 回答：

可以，下面把

$$
\frac{D\mathbf f}{Dt}=(\nabla \mathbf v)\mathbf f
$$

从

$$
\mathbf F=\frac{\partial \mathbf x}{\partial \mathbf X}
$$

一步一步推出来。

先说明记号：

- $\mathbf X$：参考构形中的材料坐标

- $\mathbf x=\chi(\mathbf X,t)$：运动

- $\mathbf F=\dfrac{\partial \mathbf x}{\partial \mathbf X}$：形变梯度

- $\mathbf v(\mathbf x,t)=\dfrac{\partial \chi}{\partial t}(\mathbf X,t)$：速度场

如果你文中的 $\mathbf f$ 就是把 $\mathbf F$ 看成当前空间中的场来写，那本质上还是同一个对象，只是自变量从 $(\mathbf X,t)$ 改写成了 $(\mathbf x,t)$。

**1. 先在拉格朗日描述下对 $\mathbf F$ 求时间导数**

由定义

$$
F_{iJ}=\frac{\partial x_i}{\partial X_J}.
$$

对时间求导：

$$
\frac{\partial F_{iJ}}{\partial t}
=
\frac{\partial}{\partial t}\left(\frac{\partial x_i}{\partial X_J}\right)
=
\frac{\partial}{\partial X_J}\left(\frac{\partial x_i}{\partial t}\right).
$$

而

$$
\frac{\partial x_i}{\partial t}=v_i(\mathbf x(\mathbf X,t),t),
$$

所以

$$
\frac{\partial F_{iJ}}{\partial t}
=
\frac{\partial}{\partial X_J}v_i(\mathbf x(\mathbf X,t),t).
$$

**2. 用链式法则把对 $\mathbf X$ 的导数改写成对 $\mathbf x$ 的导数**

因为 $v_i$ 是 $\mathbf x$ 的函数，

$$
\frac{\partial}{\partial X_J}v_i(\mathbf x(\mathbf X,t),t)
=
\frac{\partial v_i}{\partial x_k}\frac{\partial x_k}{\partial X_J}.
$$

注意

$$
\frac{\partial x_k}{\partial X_J}=F_{kJ},
$$

因此

$$
\frac{\partial F_{iJ}}{\partial t}
=
\frac{\partial v_i}{\partial x_k}F_{kJ}.
$$

写成矩阵形式就是

$$
\dot{\mathbf F}=(\nabla \mathbf v)\mathbf F.
$$

这里的点 $\dot{\mathbf F}$ 是在固定材料点 $\mathbf X$ 下的时间导数，也就是拉格朗日导数。

**3. 改写成欧拉形式，就是物质导数**

如果把 $\mathbf F$ 改写成当前空间中的场

$$
\mathbf f(\mathbf x,t)=\mathbf F(\mathbf X,t),\qquad \mathbf x=\chi(\mathbf X,t),
$$

那么沿材料轨迹求导就有

$$
\frac{D\mathbf f}{Dt}
=
\frac{d}{dt}\mathbf f(\mathbf x(t),t).
$$

而这和刚才固定 $\mathbf X$ 求导是同一件事，所以

$$
\frac{D\mathbf f}{Dt}=\dot{\mathbf F}.
$$

因此直接得到

$$
\frac{D\mathbf f}{Dt}=(\nabla \mathbf v)\mathbf f.
$$

**4. 和物质导数通式并不矛盾**

因为对任意欧拉场都成立

$$
\frac{D\mathbf f}{Dt}
=
\frac{\partial \mathbf f}{\partial t}+(\mathbf v\cdot\nabla)\mathbf f,
$$

所以对这个特殊的 $\mathbf f$ 当然也成立。于是它满足的是

$$
\frac{\partial \mathbf f}{\partial t}+(\mathbf v\cdot\nabla)\mathbf f
=
(\nabla\mathbf v)\mathbf f.
$$

也就是说：

- 左边：物质导数的通用展开

- 右边：这个特殊场“形变梯度”的具体演化规律

**5. 最直观的一句话**

$$
\mathbf F=\frac{\partial \mathbf x}{\partial \mathbf X}
$$

描述的是“材料线元怎么被映射到当前构形”；  
而

$$
\nabla \mathbf v
$$

描述的是“邻近点速度差异如何作用在线元上”；  
所以线元的演化自然由

$$
\dot{\mathbf F}=(\nabla\mathbf v)\mathbf F
$$

控制。

如果你愿意，我可以继续给你推导一下为什么线元满足

$$
\frac{D(d\mathbf x)}{Dt}=(\nabla\mathbf v)\,d\mathbf x
$$

以及它和 $\mathbf F$ 的关系，这样直觉会更清楚。
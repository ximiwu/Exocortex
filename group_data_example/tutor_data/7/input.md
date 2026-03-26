第 3 段：速度和加速度的欧拉版本

拉格朗日速度与加速度是

$$\mathbf{V}(\mathbf{X},t),\qquad \mathbf{A}(\mathbf{X},t).$$

推前后定义欧拉速度与加速度：

$$\mathbf{v}(\mathbf{x},t)=\mathbf{V}(\phi^{-1}(\mathbf{x},t),t),$$ $$\mathbf{a}(\mathbf{x},t)=\mathbf{A}(\phi^{-1}(\mathbf{x},t),t).$$

这表示：在空间点 $\mathbf{x}$ 观测到的速度，等于“此刻恰好位于这里的那块材料”的拉格朗日速度。

反过来，也有

$$\mathbf{V}(\mathbf{X},t)=\mathbf{v}(\phi(\mathbf{X},t),t),$$ $$\mathbf{A}(\mathbf{X},t)=\mathbf{a}(\phi(\mathbf{X},t),t).$$
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

5. 5.4 Material Derivative：物质导数
第 1 段：物质导数的定义与直觉

为了把上一节的结果写得更简洁，定义：

$$\frac{D}{Dt}\mathbf{v} = \frac{\partial \mathbf{v}}{\partial t} + (\mathbf{v}\cdot\nabla)\mathbf{v}.$$

于是

$$\mathbf{a}=\frac{D\mathbf{v}}{Dt}.$$

物质导数不是某种神秘新算子，它本质上就是：

$$\frac{D}{Dt}f(\mathbf{x},t) = \frac{d}{dt}f(\mathbf{x}(t),t), \qquad \text{其中 } \dot{\mathbf{x}}(t)=\mathbf{v}(\mathbf{x}(t),t).$$

也就是说，$\frac{D}{Dt}$ 表示沿材料轨迹求导。

# 历史对话：


## 提问：

为啥物质导数本质上就是$\frac{D}{Dt}f(\mathbf{x},t) = \frac{d}{dt}f(\mathbf{x}(t),t), \qquad \text{其中 } \dot{\mathbf{x}}(t)=\mathbf{v}(\mathbf{x}(t),t).$

## 回答：

因为它就是普通多元函数的链式法则。

设 $f(\mathbf{x},t)$ 是一个欧拉场，材料点的轨迹记作

$$
\mathbf{x}(t), \qquad \dot{\mathbf{x}}(t)=\mathbf{v}(\mathbf{x}(t),t).
$$

那么沿着这条轨迹看 $f$，实际上是在看单变量函数

$$
t\mapsto f(\mathbf{x}(t),t).
$$

对它求导，按链式法则：

$$
\frac{d}{dt}f(\mathbf{x}(t),t)
=
\frac{\partial f}{\partial t}(\mathbf{x}(t),t)

+
\nabla f(\mathbf{x}(t),t)\cdot \dot{\mathbf{x}}(t).
$$

再代入轨迹速度

$$
\dot{\mathbf{x}}(t)=\mathbf{v}(\mathbf{x}(t),t),
$$

得到

$$
\frac{d}{dt}f(\mathbf{x}(t),t)
=
\frac{\partial f}{\partial t}(\mathbf{x}(t),t)

+
\mathbf{v}(\mathbf{x}(t),t)\cdot \nabla f(\mathbf{x}(t),t).
$$

这正是

$$
\frac{D f}{D t}
=
\frac{\partial f}{\partial t}+(\mathbf{v}\cdot\nabla)f
$$

在材料轨迹上的表达。

所以物质导数并不是什么额外定义出来的神秘东西，它就是：

- $\partial f/\partial t$：固定空间点看到的变化；

- $(\mathbf{v}\cdot\nabla)f$：材料点因为自己移动到别处而额外经历到的变化。

两者相加，就等于“跟着材料点走时，$f$ 的真实变化率”。

如果你愿意，我可以把这段整理成一版适合直接放进讲义的、更顺滑的中文表述。
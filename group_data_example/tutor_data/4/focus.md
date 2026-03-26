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
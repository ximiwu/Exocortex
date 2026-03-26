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
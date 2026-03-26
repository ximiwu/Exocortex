第 2 段：形变梯度 $\mathbf{F}$ 的定义

最核心的定义来了：

$$\mathbf{F}(\mathbf{X},t)=\frac{\partial \phi}{\partial \mathbf{X}}(\mathbf{X},t) =\frac{\partial \mathbf{x}}{\partial \mathbf{X}}(\mathbf{X},t).$$

这就是形变梯度。

从第一性原理看，$\mathbf{F}$ 就是映射 $\phi$ 在局部的一阶线性近似。对任意很小的材料位移 $d\mathbf{X}$，有

$$\phi(\mathbf{X}+d\mathbf{X},t) \approx \phi(\mathbf{X},t)+\mathbf{F}(\mathbf{X},t)\,d\mathbf{X}.$$

因此

$$d\mathbf{x}\approx \mathbf{F}\,d\mathbf{X}.$$

这句话比“$\mathbf{F}$ 是 Jacobian”更重要。它告诉你：

$\mathbf{F}$ 真正描述的是局部邻域中的线元、切向量、微小边长如何被变换。

如果说 $\mathbf{x}=\phi(\mathbf{X},t)$ 讲的是“这个材料点最后到了哪里”，那么 $\mathbf{F}$ 讲的就是“这个材料点周围那个无穷小小方块被揉成了什么样”。

第 3 段：分量形式与维数含义

分量形式是：

$$F_{ij}=\frac{\partial x_i}{\partial X_j}.$$

含义是：参考方向第 $j$ 个基向量的变化，会如何影响当前坐标的第 $i$ 个分量。

如果是三维实体，$\mathbf{F}$ 通常是 $3\times 3$；如果是嵌入三维空间中的二维薄壳/布料，材料本身只有二维参数坐标，所以 $\mathbf{F}$ 可以是 $3\times 2$。

这暴露了一个常被忽略的事实：
$\mathbf{F}$ 的列数对应材料的内禀维数，行数对应嵌入空间维数。
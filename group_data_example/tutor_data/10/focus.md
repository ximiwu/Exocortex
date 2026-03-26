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
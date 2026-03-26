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

# 历史对话：


## 提问：

phi和X应该是三维向量，然后向量对向量求偏导的规则是啥

## 回答：

是的，在标准三维连续介质里，$\mathbf X$ 和 $\phi(\mathbf X,t)=\mathbf x$ 都可以看成三维向量。但“向量对向量求偏导”本质上不是一个新的奇怪运算，它就是把每个分量分别求偏导，组成一个矩阵，也就是 Jacobian。

设

$$
\mathbf X=(X_1,X_2,X_3)^T,\qquad
\mathbf x=\phi(\mathbf X,t)=
\begin{pmatrix}
x_1(X_1,X_2,X_3,t)\
x_2(X_1,X_2,X_3,t)\
x_3(X_1,X_2,X_3,t)
\end{pmatrix}.
$$

那么

$$
\frac{\partial \mathbf x}{\partial \mathbf X}
$$

定义为

$$
\left[\frac{\partial x_i}{\partial X_j}\right]
=
\begin{pmatrix}
\frac{\partial x_1}{\partial X_1} & \frac{\partial x_1}{\partial X_2} & \frac{\partial x_1}{\partial X_3}\
\frac{\partial x_2}{\partial X_1} & \frac{\partial x_2}{\partial X_2} & \frac{\partial x_2}{\partial X_3}\
\frac{\partial x_3}{\partial X_1} & \frac{\partial x_3}{\partial X_2} & \frac{\partial x_3}{\partial X_3}
\end{pmatrix}.
$$

这就是形变梯度

$$
\mathbf F=\frac{\partial \phi}{\partial \mathbf X}=\frac{\partial \mathbf x}{\partial \mathbf X}.
$$

最核心的规则就是：

$$
d\mathbf x=\mathbf F\,d\mathbf X
$$

在线性近似下成立。

也就是说：

- 输入是一个微小材料线元 $d\mathbf X$

- 输出是它变形后的微小空间线元 $d\mathbf x$

- $\mathbf F$ 是两者之间的线性映射

所以“向量对向量求偏导”可以理解成：

- 列 $j$：沿参考坐标 $X_j$ 方向变化时，$\mathbf x$ 怎么变

- 行 $i$：当前坐标分量 $x_i$ 对各个参考坐标的敏感度

更抽象一点，若

$$
\mathbf f:\mathbb R^n\to\mathbb R^m,
$$

则

$$
\frac{\partial \mathbf f}{\partial \mathbf X}
$$

就是一个 $m\times n$ 矩阵，元素为

$$
\left(\frac{\partial \mathbf f}{\partial \mathbf X}\right)_{ij}
=
\frac{\partial f_i}{\partial X_j}.
$$

所以：

- 三维实体：$\mathbf F\in\mathbb R^{3\times 3}$

- 二维曲面嵌入三维：$\mathbf F\in\mathbb R^{3\times 2}$

如果你愿意，我可以继续给你讲一下“为什么有些书里分母布局/分子布局看起来会转置”，也就是不同 Jacobian 记号约定的问题。

## 提问：

为啥x是横着放的

## 回答：

不是说 `x` 本身“必须横着放”，而是这里写

$$
\frac{\partial \mathbf x}{\partial \mathbf X}
$$

时，作者实际上是在用一种约定：把结果定义成矩阵

$$
\left[\frac{\partial x_i}{\partial X_j}\right].
$$

这个定义直接保证了

$$
d\mathbf x=\mathbf F\,d\mathbf X
$$

在列向量记号下成立。

更具体地说：

- 若把

$$
\mathbf X=(X_1,X_2,X_3)^T,\quad \mathbf x=(x_1,x_2,x_3)^T
$$

都看成列向量，

- 那么形变梯度就定义为

$$
\mathbf F_{ij}=\frac{\partial x_i}{\partial X_j}.
$$

- 于是对微分有

$$
dx_i=\sum_j \frac{\partial x_i}{\partial X_j}dX_j,
$$

合起来就是

$$
d\mathbf x=\mathbf F\,d\mathbf X.
$$

你觉得“`x` 为什么像横着放”，其实是因为 Jacobian 写成

$$
\frac{\partial \mathbf x}{\partial \mathbf X}
$$

时，分子分母只是记号，不是真的在做“向量除法”。它只是表示：

- 对输出向量 `x` 的每个分量求导

- 再按 $(i,j)$ 排成矩阵

所以不是“`x` 横着放了”，而是“导数结果要组织成一个矩阵”。

很多困惑来自不同书的约定不同：

1. `分母布局`

$$
J_{ij}=\frac{\partial x_i}{\partial X_j}
$$

这是连续介质里最常见的，因为它让

$$
d\mathbf x=J\,d\mathbf X
$$

很自然。

2. `分子布局`
有些书会写成转置形式，即把 Jacobian 定义成

$$
J_{ij}=\frac{\partial x_j}{\partial X_i},
$$

那就会和上面的矩阵差一个转置。

所以核心不是 `x` 横着还是竖着，而是：

- 你把向量当列向量还是行向量

- 你采用哪种 Jacobian 排列约定

在你这里，为了让

$$
d\mathbf x=\mathbf F\,d\mathbf X
$$

成立，最自然的就是把 $\mathbf x,\mathbf X$ 都当列向量，而

$$
\mathbf F=\left[\frac{\partial x_i}{\partial X_j}\right].
$$

如果你愿意，我可以接着专门画一个“行向量/列向量/Jacobian 转置”对照表，一眼就能看懂。
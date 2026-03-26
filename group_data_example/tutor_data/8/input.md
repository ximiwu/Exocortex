第 1 段：为什么体积变化由行列式控制

这里考虑参考构形中一个无限小体元 $dV$。若其三条边是 $d\mathbf{L}_1,d\mathbf{L}_2,d\mathbf{L}_3$，则体积可写成标量三重积：

$$dV=d\mathbf{L}_1\cdot(d\mathbf{L}_2\times d\mathbf{L}_3).$$

变形后，这三条边变成

$$d\mathbf{l}_i=\mathbf{F}d\mathbf{L}_i.$$

于是当前体积为

$$dv = d\mathbf{l}_1\cdot(d\mathbf{l}_2\times d\mathbf{l}_3) = \det(\mathbf{F})\,dV = J\,dV.$$

这不是巧合，而是行列式最本质的几何意义：
线性变换对体积的缩放因子就是其行列式。
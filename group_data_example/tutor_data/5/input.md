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

详细解释一下$\mathbf{a}\neq \partial \mathbf{v}/\partial t$

## 回答：

关键不是“两个符号长得像不像”，而是它们的导数对象不同。

$$
\mathbf a(\mathbf x,t)\neq \frac{\partial \mathbf v}{\partial t}(\mathbf x,t)
$$

这句话的本质是：

- $\dfrac{\partial \mathbf v}{\partial t}$ 是“站在空间中某个固定位置不动”看速度怎么随时间变。

- $\mathbf a$ 是“跟着某个流体质点一起移动”时，这个质点实际感受到的速度变化率。

这两个过程不是一回事，所以一般不相等。

---

**1. 固定点看 vs 跟着粒子看**

速度场是

$$
\mathbf v=\mathbf v(\mathbf x,t)
$$

它依赖两个变量：位置 $\mathbf x$ 和时间 $t$。

如果你取一个固定空间点 $\mathbf x_0$，那么

$$
\frac{\partial \mathbf v}{\partial t}(\mathbf x_0,t)
$$

表示“这个位置上的流速随时间怎么变”。

但流体质点不会停在 $\mathbf x_0$。它有轨迹 $\mathbf x(t)$，满足

$$
\dot{\mathbf x}(t)=\mathbf v(\mathbf x(t),t).
$$

于是这个质点真正经历的速度是

$$
\mathbf v(\mathbf x(t),t),
$$

它的加速度应当是沿轨迹的全导数：

$$
\mathbf a=\frac{d}{dt}\mathbf v(\mathbf x(t),t).
$$

这里必须同时考虑两种变化：

- 时间本身变了；

- 质点的位置也变了。

所以链式法则给出

$$
\frac{d}{dt}\mathbf v(\mathbf x(t),t)
=
\frac{\partial \mathbf v}{\partial t}
+
(\nabla \mathbf v)\,\dot{\mathbf x}(t).
$$

再代入 $\dot{\mathbf x}(t)=\mathbf v$，得到

$$
\mathbf a
=
\frac{\partial \mathbf v}{\partial t}
+
(\mathbf v\cdot\nabla)\mathbf v.
$$

因此

$$
\boxed{\mathbf a=\frac{\partial \mathbf v}{\partial t}+(\mathbf v\cdot\nabla)\mathbf v}
$$

一般当然不等于 $\partial \mathbf v/\partial t$。

---

**2. 多出来的项到底在说什么**

多出来的

$$
(\mathbf v\cdot\nabla)\mathbf v
$$

叫对流项。

它表示：即使流场在每个固定点上都“不随时间变化”，一个流体质点仍然会因为自己移动到了别的位置，而看到不同的速度。

也就是说：

- $\partial \mathbf v/\partial t$：记录“原地等待”看到的变化；

- $(\mathbf v\cdot\nabla)\mathbf v$：记录“边走边看”多出来的变化。

所以 $\mathbf a\neq \partial \mathbf v/\partial t$ 的原因非常直接：流体质点不是静止观察者，它会穿过空间上速度不同的区域。

---

**3. 一个一维例子最清楚**

设一维速度场

$$
v(x)=x,\qquad \frac{\partial v}{\partial t}=0.
$$

这说明这是个稳态流场，在每个固定位置看，速度都不随时间变。

但对流体质点来说，它满足

$$
\frac{dx}{dt}=v(x)=x.
$$

质点速度是 $v(x(t))=x(t)$，所以它的加速度为

$$
a=\frac{dv}{dt}=\frac{d}{dt}x(t)=x(t).
$$

或者按公式算：

$$
a=\frac{\partial v}{\partial t}+v\frac{\partial v}{\partial x}
=0+x\cdot 1=x.
$$

所以这里

$$
a=x\neq 0,\qquad \frac{\partial v}{\partial t}=0.
$$

这正说明：

- 固定点看：没变化；

- 跟着粒子走：有加速度。

原因只是它走到了更大的 $x$，那里速度更大。

---

**4. 为什么这不矛盾**

很多人觉得“不直观”，是因为把“速度场随时间变化”误当成了“粒子速度变化”。

但其实：

- 场是定义在整个空间上的；

- 粒子只沿着其中一条轨迹运动。

即使场在固定点处不变，粒子仍可能因为换了位置而获得不同速度。

类比一下：

你站在桥上看河，桥下某一点的流速始终是 $2\,\text{m/s}$，所以该点的 $\partial \mathbf v/\partial t=0$。  
但一片树叶顺流而下，可能从慢水区漂到快水区，于是它的速度从 $1$ 变成 $3\,\text{m/s}$。  
树叶有加速度，但桥上某固定点的流速却没随时间变。

这完全不冲突，因为两者观察方式不同。

---

**5. 什么时候才会相等**

只有在对流项消失时，才有

$$
\mathbf a=\frac{\partial \mathbf v}{\partial t}.
$$

例如：

- 流体质点恰好静止，$\mathbf v=0$；

- 速度场空间上均匀，$\nabla \mathbf v=0$；

- 或更一般地，$(\mathbf v\cdot\nabla)\mathbf v=0$。

否则一般都不相等。

---

**6. 一句话总结**

$$
\frac{\partial \mathbf v}{\partial t}
$$

是“固定位置的局部变化率”，而

$$
\mathbf a=\frac{D\mathbf v}{Dt}
$$

是“沿着流体质点轨迹的物质导数”。  
两者之差正是质点因为在空间中移动而额外经历到的变化：

$$
\mathbf a-\frac{\partial \mathbf v}{\partial t}
=
(\mathbf v\cdot\nabla)\mathbf v.
$$

如果你愿意，我还可以继续把这个区别画成一个“拉格朗日视角 vs 欧拉视角”的示意图，或者用分量形式把 $(\mathbf v\cdot\nabla)\mathbf v$ 逐项展开解释。
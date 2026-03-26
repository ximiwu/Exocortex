# 5 KINEMATICS THEORY

The contents in this section mostly follow [Bonet and Wood, 2008]. We summarize the important concepts that are helpful for understanding the essence of MPM.

First and foremost, MPM particles are not individual particles, molecules, atoms or little spheres as one may naturally think when seeing a "particle" method. Each MPM particle actually represents a continuous piece of material, or really a subset of the whole simulated material domain. For those familiar with FEM style weak forms of equations, material points can be thought of as quadrature points for the discretization of spatial stress derivatives (we will talk about the discretization in Section 9).

Such a view is very common in computational mechanics. When we talk about continuum bodies or continuum mechanics, we have adopted the continuum assumption. This means the studied material (either solid, liquid or gas) is treated as continuous pieces of matter. Such a view is very practical in engineering and graphics applications (as well as in everyday life) where it is really not necessary to deal with the microscopic inter

actions between molecules and atoms. Note that a continuum assumption can be made for almost all solids and fluids that are extensively simulated for graphics, including deformable (elastic and plastic) objects, muscle, flesh, cloth, hair, liquids, smoke, gas and granular materials (sand, snow, mud, soil etc.). A continuum body defines quantities such as density, velocity, and force as continuous functions of position. Equations of motion are solved in the spatial domain, and evolved in time to simulate the behaviors of the simulated materials.

# 5.1 Continuum Motion

Kinematics refers to the study of motion occurred in continuum materials. The main focus is the change of shape, or the deformation, either locally or globally in different coordinate systems of interest. Describing the motion qualitatively and quantitatively is very essential for deriving governing equations of dynamics and mechanical responses. Luckily in most cases, we can describe kinematics without introducing the meaning of force, stress or even mass.

In continuum mechanics, the deformation is usually represented with the material (or undeformed) space  $\mathbf{X}$ , the world (or deformed) space  $\mathbf{x}$  and a deformation map  $\phi(\mathbf{X}, t)$ . You can simply treat  $\mathbf{X}$  as the "initial position" and  $\mathbf{x}$  as the "current position" for any point in the simulated material. In particular, at time  $t = 0$ ,  $\mathbf{X}$  and  $\mathbf{x}$  have the same value.

Here is a more detailed definition. We consider the motion of material to be determined by a mapping  $\phi(\cdot, t): \Omega^0 \to \Omega^t$  for  $\Omega^0, \Omega^t \subset \mathbb{R}^d$  where  $d = 2$  or 3 is the dimension of the simulated problem (or domain). The mapping  $\phi$  is sometimes called the flow map or the deformation map. Points in the set  $\Omega^0$  are referred to as material points and are denoted as  $\mathbf{X}$ . Points in  $\Omega^t$  represent the location of material points at time  $t$ . They are referred to as  $\mathbf{x}$ . In other words,  $\phi$  describes the motion of each material point  $\mathbf{X} \in \Omega^0$  over time

$$
\mathbf {x} = \mathbf {x} (\mathbf {X}, t) = \phi (\mathbf {X}, t). \tag {1}
$$

For example, if our object is moving with a constant speed  $\nu$  along direction  $\mathsf{n}$ , then we have

$$
x = X + t v n. \tag {2}
$$

If an object went through some rigid motion after time  $t$  (compared to time 0), we will have

$$
\mathbf {x} = \mathbf {R} \mathbf {X} + \mathbf {b}, \tag {3}
$$

where  $\mathbf{R}$  is a rotation matrix,  $\mathbf{b}$  is some translation.  $\mathbf{R}$  and  $\mathbf{b}$  will probably be some function with respect to time  $t$  and initial position  $\mathbf{X}$ , depending on the actual motion.

This mapping can be used to quantify the relevant continuum based physics. For example, the velocity of a given material point  $\mathbf{X}$  at time  $t$  is

$$
\mathbf {V} (\mathbf {X}, t) = \frac {\partial \phi}{\partial t} (\mathbf {X}, t) \tag {4}
$$

also the acceleration is

$$
\mathbf {A} (\mathbf {X}, t) = \frac {\partial^ {2} \phi}{\partial t ^ {2}} (\mathbf {X}, t) = \frac {\partial \mathbf {V}}{\partial t} (\mathbf {X}, t). \tag {5}
$$

I.e.  $\mathbf{V}(\cdot ,t):\Omega^0\to \mathbb{R}^d$  and  $\mathbf{A}(\cdot ,t):\Omega^0\to \mathbb{R}^d$

The velocity  $\mathbf{V}$  and acceleration  $\mathbf{A}$  defined above are based on the "Lagrangian view", where they are functions of the material configuration  $\mathbf{X}$  and time  $t$ . Physically, this means we are measuring them on a fixed particle. This particle has its mass and occupies some volume since the beginning. This is an important concept, because soon we will encounter the "Eulerian view", where we are sitting at a fixed position in the space and measuring the velocity of whichever particle that is passing by that position. For example, the flow velocity in a grid based fluid simulation is a typical Eulerian viewed quantity. For solid simulation and continuum mechanics, it is often more natural (but not necessary) to start from the Lagrangian view for deriving stuff.

# 5.2 Deformation

Now we have  $\mathbf{X}$  and  $\mathbf{x}$  being material coordinates and world coordinates, and they belong to domain  $\Omega_0$  and  $\Omega_{\mathrm{t}}$  respectively. For any point  $\mathbf{X}$  in  $\Omega_0$ , we also have  $\Phi$  to map it to  $\Omega_{\mathrm{t}}$  for a given time  $\mathbf{t}$  via  $\mathbf{x} = \Phi (\mathbf{X},\mathbf{t})$ .

The Jacobian of the deformation map  $\phi$  is useful for a number of reasons described below. E.g. the physics of elasticity is naturally described in terms of this Jacobian. It is standard notation to use  $\mathbf{F}$  to refer to the Jacobian of the deformation mapping

$$
\mathbf {F} (\mathbf {X}, t) = \frac {\partial \phi}{\partial \mathbf {X}} (\mathbf {X}, t) = \frac {\partial x}{\partial \mathbf {X}} (\mathbf {X}, t). \tag {6}
$$

$\mathsf{F}$  is often simply called the deformation gradient. Discretely it is often a small  $2 \times 2$  or  $3 \times 3$  matrix. One special case is for a cloth/thin shell in  $3\mathrm{D}$ ,  $\mathsf{F}$  is  $3 \times 2$  because the material space is really just  $2\mathrm{D}$ . It can be thought of as  $\mathsf{F}(\cdot, \mathsf{t}): \Omega^0 \to \mathbb{R}^{d \times d}$ . In other words, for every material point  $\mathbf{X}$ ,  $\mathsf{F}(\mathbf{X}, \mathsf{t})$  is the  $\mathbb{R}^{d \times d}$  matrix describing the deformation Jacobian of the material at time  $t$ . We can also use the index notation

$$
F _ {i j} = \frac {\partial \phi_ {i}}{\partial X _ {j}} = \frac {\partial x _ {i}}{\partial X _ {j}}, i, j = 1, \dots , d. \tag {7}
$$

Now we can compute the deformation gradient of the deformation map in Equation 2. The result is the identity matrix. For the one in Equation 3 we get  $\mathbf{F} = \mathbf{R}$ . In both

### Figure 1 Content

#### Mapping of Configurations
The figure illustrates a continuous transformation between two states of a material body. On the left is the initial or reference configuration, denoted as $\Omega^0$, and on the right is the current or deformed configuration, denoted as $\Omega$. A prominent black arrow labeled $\mathbf{F}$ indicates the mapping function—the deformation gradient—that relates the two states.

#### Local Deformation of Material Points
Within the reference configuration $\Omega^0$, two specific material points are identified: $\mathbf{x}_1^0$ and $\mathbf{x}_2^0$. They are connected by a vertical straight-line segment. In the deformed configuration $\Omega$, these same material points are now located at $\mathbf{x}_1$ and $\mathbf{x}_2$. The line segment connecting them has undergone a change in both orientation (it is now tilted) and relative distance, visually demonstrating how the local geometry of the material is altered by the transformation $\mathbf{F}$.

#### Global Geometric Change
Beyond the individual points, the entire boundary of the region has changed shape between $\Omega^0$ and $\Omega$. The reference shape $\Omega^0$ appears more symmetric and vertically oriented, while the deformed shape $\Omega$ is elongated and skewed to the right, representing a combination of rotation, stretching, and shearing of the material volume.  
Figure 1: Deformation gradient.

these cases, we know the object does not really deform because all they did are rigid transformations. Such deformation gradients should not result in any internal forces in the material unless artistic effects are desired.

Intuitively, the deformation gradient represents how deformed a material is locally. For example, let  $x_1^0$  and  $x_2^0$  be two nearby points embedded in the material (see Figure 1) at the beginning of the simulation, and let  $x_1$  and  $x_2$  be the same two points in the current configuration. Then  $(x_2 - x_1) = F(x_2^0 - x_1^0)$ .

The determinant of  $\mathsf{F}$  (commonly denoted with  $\mathbf{J}$ ) is also often useful because it characterizes infinitesimal volume change. It is commonly denoted with  $\mathbf{J} = \det(\mathbf{F})$ .  $\mathbf{J}$  is the ratio of the infinitesimal volume of material in configuration  $\Omega^{\mathrm{t}}$  to the original volume in  $\Omega^0$ . As an example, it is easy to see for rigid motions (rotations and translations),  $\mathbf{F}$  is a rotation matrix and  $\mathbf{J} = 1$ . Note that identity matrix is also a rotation matrix.  $\mathbf{J} > 1$  means volume increase and  $\mathbf{J} < 1$  means decrease.

$J = 0$  means the volume becomes zero. In the real world, this will never happen. However, numerically it is possible to achieve such an  $F$ . In  $3D$ , that suggests the material is so compressed that it becomes a plane or a line or a single volumeless point.  $J < 0$  means the material is inverted. Consider a triangle in  $2D$ ,  $J < 0$  means one vertex passes through its opposing edge, and the area of this triangle becomes negative. Invertible elasticity [Irving et al., 2004; Stomakhin et al., 2012] is one of the popular methods for resolving these cases. The model we will talk about in Section 6 for snow will be fine with these degenerate cases due to its nice numerical properties.

# 5.3 Push Forward and Pull Back

So far we have assumed quantities are in terms of  $(\mathbf{X},\mathbf{t})$ , this is called the Lagrangian view. The mapping  $\phi$  is assumed to be bijective. And since we will assume it is smooth,

this means that the sets  $\Omega^0$  and  $\Omega^{\mathrm{t}}$  are homeomorphic/diffeomorphic under  $\phi$ . This is associated with the assumption that no two different particles of material ever occupy the same space at the same time. This means that  $\forall \mathbf{x} \in \Omega^{\mathrm{t}}$ ,  $\exists !\mathbf{X} \in \Omega^0$  such that  $\phi(\mathbf{X}, \mathbf{t}) = \mathbf{x}$ . In other words, there exist an inverse mapping  $\phi^{-1}(\cdot, \mathbf{t}): \Omega^{\mathrm{t}} \to \Omega^0$ . This means that any function over one set can naturally be thought of as a function over the other set by means of change of variables. We denote this interchange of independent variable as either push forward (taking a function defined over  $\Omega^0$  and defining a counterpart over  $\Omega^{\mathrm{t}}$ ) or vice versa (pull back). For example, given  $\mathsf{G}: \Omega^0 \to \mathbb{R}$  the push forward  $g(\cdot, \mathbf{t}): \Omega^{\mathrm{t}} \to \mathbb{R}$  is defined as  $g(\mathbf{x}, \mathbf{t}) = \mathsf{G}(\phi^{-1}(\mathbf{x}, \mathbf{t}))$ . Similarly, the pull back of  $\mathbf{g}$  is  $\mathsf{G}(\mathbf{X}) = g(\phi(\mathbf{X}, \mathbf{t}), \mathbf{t})$  which can be seen to be exactly  $\mathsf{G}(\mathbf{X})$  by definition of the inverse mapping.

The push forward of a function is sometimes referred to as Eulerian (a function of  $x$ ) and the pull back function is sometimes referred to as Lagrangian (a function of  $X$ ). As previously defined in Equation 4 and 5, the velocity and acceleration functions are Lagrangian. Let's rewrite them here:

$$
\mathbf {V} (\mathbf {X}, t) = \frac {\partial \phi}{\partial t} (\mathbf {X}, t) \tag {8}
$$

$$
\boldsymbol {A} (\boldsymbol {X}, t) = \frac {\partial^ {2} \phi}{\partial t ^ {2}} (\boldsymbol {X}, t) = \frac {\partial \boldsymbol {V}}{\partial t} (\boldsymbol {X}, t). \tag {9}
$$

It is also useful to define Eulerian counterparts. That is, using push forward,

$$
\boldsymbol {v} (\boldsymbol {x}, t) = \boldsymbol {V} \left(\phi^ {- 1} (\boldsymbol {x}, t), t\right), \tag {10}
$$

$$
\mathbf {a} (\mathbf {x}, t) = \mathbf {A} \left(\phi^ {- 1} (\mathbf {x}, t), t\right). \tag {11}
$$

With this, we can also see that the pull back formula are

$$
\mathbf {V} (\mathbf {X}, t) = \mathbf {v} (\phi (\mathbf {X}, t), t), \tag {12}
$$

$$
\mathbf {A} (\mathbf {X}, t) = \mathbf {a} (\phi (\mathbf {X}, t), t). \tag {13}
$$

With this notion of  $\mathbf{a}$  and  $\mathbf{v}$  we can see that (using chain rule)

$$
\mathbf {A} (\mathbf {X}, t) = \frac {\partial}{\partial t} \mathbf {V} (\mathbf {X}, t) = \frac {\partial \mathbf {v}}{\partial t} (\phi (\mathbf {X}, t), t) + \frac {\partial \mathbf {v}}{\partial x} (\phi (\mathbf {X}, t), t) \frac {\partial \phi}{\partial t} (\mathbf {X}, t). \tag {14}
$$

Using index notation, this can be written as

$$
A _ {i} (\mathbf {X}, t) = \frac {\partial}{\partial t} V _ {i} (\mathbf {X}, t) = \frac {\partial v _ {i}}{\partial t} (\phi (\mathbf {X}, t), t) + \frac {\partial v _ {i}}{\partial x _ {j}} (\phi (\mathbf {X}, t), t) \frac {\partial \phi_ {j}}{\partial t} (\mathbf {X}, t). \tag {15}
$$

where summation is implied on the repeated index  $j$ .

Combining Equation 8 and 10, we have

$$
v _ {j} (\mathbf {x}, t) = \frac {\partial \phi_ {j}}{\partial t} \left(\phi^ {- 1} (\mathbf {x}, t), t\right). \tag {16}
$$

Combining Equation 11 and 15, we have

$$
a _ {i} (\boldsymbol {x}, t) = A _ {i} \left(\phi^ {- 1} (\boldsymbol {x}, t), t\right) = \frac {\partial v _ {i}}{\partial t} (\boldsymbol {x}, t) + \frac {\partial v _ {i}}{\partial x _ {j}} (\boldsymbol {x}, t) v _ {j} (\boldsymbol {x}, t) \tag {17}
$$

where we used  $x = \phi (\phi^{-1}(x,t),t)$  (by definition).

We thus get a seemingly non-intuitive result:

$$
a _ {i} (x, t) \neq \frac {\partial v _ {i}}{\partial t} (x, t). \tag {18}
$$

# 5.4 Material Derivative

Although the relationship between the Eulerian  $\mathbf{a}$  and  $\mathbf{v}$  is not simply via partial differentiation with respect to time, the relationship is a common one and it is often called the material derivative. The notation

$$
\frac {D}{D t} v _ {i} (x, t) = \frac {\partial v _ {i}}{\partial t} (x, t) + \frac {\partial v _ {i}}{\partial x _ {j}} (x, t) v _ {j} (x, t) \tag {19}
$$

is often introduced so that

$$
\mathbf {a} = \frac {\mathrm {D}}{\mathrm {D} t} \mathbf {v}. \tag {20}
$$

For a general Eulerian function  $f(\cdot, t): \Omega^t \to \mathbb{R}$ , we use this same notation to mean

$$
\frac {\mathrm {D}}{\mathrm {D} t} f (\boldsymbol {x}, t) = \frac {\partial f}{\partial t} (\boldsymbol {x}, t) + \frac {\partial f}{\partial x _ {\mathrm {j}}} (\boldsymbol {x}, t) v _ {\mathrm {j}} (\boldsymbol {x}, t). \tag {21}
$$

Note that  $\frac{\mathrm{D}}{\mathrm{D}t}\mathsf{f}(\mathbf{x},t)$  is the push forward of  $\frac{\partial}{\partial t}\mathsf{F}$  where  $\mathsf{F}$  is a Lagrangian function with  $\mathsf{F}(\cdot ,t):\Omega^0\to \mathbb{R}$ .  $\mathsf{F}$  is the pull back of  $\mathsf{f}$ . This rule of pushing forward  $\frac{\partial}{\partial t}\mathsf{F}(\mathbf{X},t)$  to  $\frac{\mathrm{D}}{\mathrm{D}t}\mathsf{f}(\mathbf{x},t)$  is very useful, and should always be kept in mind.

The deformation gradient is usually thought of as Lagrangian. That is, most of the time when this comes up in the physics of a material, the Lagrangian view is the dominant one. There is however a useful evolution of the Eulerian (push forward) of  $\mathsf{F}(\cdot ,\mathsf{t}):\Omega^0\to \mathbb{R}^{d\times d}$ . Let  $\mathsf{f}(\cdot ,\mathsf{t}):\Omega^{\mathsf{t}}\to \mathbb{R}^{\mathsf{d}\times \mathsf{d}}$  be the push forward of  $\mathsf{F}$ , then

$$
\frac {D}{D t} \mathbf {f} = \frac {\partial \mathbf {v}}{\partial x} \mathbf {f} \text {o r} \frac {D}{D t} f _ {i j} = \frac {\partial v _ {i}}{\partial x _ {k}} f _ {k j} \tag {22}
$$

with summation implied on the repeated index  $k$ . We can see this because

$$
\frac {\partial}{\partial t} F _ {i j} (\mathbf {X}, t) = \frac {\partial}{\partial t} \frac {\partial \phi_ {i}}{\partial X _ {j}} (\mathbf {X}, t) = \frac {\partial V _ {i}}{\partial X _ {j}} (\mathbf {X}, t) = \frac {\partial v _ {i}}{\partial x _ {k}} (\phi (\mathbf {X}, t), t) \frac {\partial \phi_ {k}}{\partial X _ {j}} (\mathbf {X}, t), \tag {23}
$$

where the last equality comes from differentiating Equation 12. In some literature (including [Bonet and Wood, 2008] and [Klar et al., 2016]), Equation 22 is written using symbol  $\mathsf{F}$  instead of  $\mathsf{f}$  as

$$
\dot {\mathbf {F}} = (\nabla \mathbf {v}) \mathbf {F} \quad \text {o r} \quad \frac {\mathrm {D} \mathbf {F}}{\mathrm {D} t} = (\nabla \mathbf {v}) \mathbf {F}, \tag {24}
$$

while the formula  $\dot{\mathbf{F}} = \frac{\partial}{\partial\mathbf{X}}\left(\frac{\partial\phi}{\partial\mathbf{t}}\right)$  also appears. When written in such ways,  $\mathbf{F}$  and  $\mathbf{f}$  are undistinguished and  $\dot{\mathbf{F}}$  is used for both time derivatives in the two spaces. It is fine to do so as long as  $\mathbf{F} = \mathbf{F}(\mathbf{X},\mathbf{t})$  or  $\mathbf{F} = \mathbf{F}(\mathbf{x},\mathbf{t})$  is clearly specified in the context. Otherwise, we prefer to keep using  $\mathbf{F}$  to denote the Lagrangian one, and  $\mathbf{f}$  for the Eulerian one to avoid confusion.

Equation 23 will play an important role in deriving the discretized  $\mathsf{F}$  update on each MPM particle (Section 9.4).

# 5.5 Volume and Area Change

Assume there is a tiny volume  $\mathrm{dV}$  at the material space, what is the corresponding value of  $\mathrm{d}\nu$  in the world space? Consider  $\mathrm{dV}$  being defined over the standard basis vectors  $\mathbf{e}_1, \mathbf{e}_2, \mathbf{e}_3$  with  $\mathrm{dV} = \mathrm{dL}_1 \mathbf{e}_1 \cdot (\mathrm{dL}_2 \mathbf{e}_2 \times \mathrm{dL}_3 \mathbf{e}_3)$ , where  $\mathrm{dL}_i$  are tiny numbers,  $\mathrm{dL}_i = \mathrm{dL}_i \mathbf{e}_i$ . Then we have

$$
\mathrm {d V} = \mathrm {d L} _ {1} \mathrm {d L} _ {2} \mathrm {d L} _ {3}. \tag {25}
$$

The corresponding deformed vectors in the world space are

$$
\mathrm {d l} _ {i} = \mathrm {F} \mathrm {d L} _ {i}. \tag {26}
$$

It can be shown that  $\mathrm{d}l_{1}\mathrm{d}l_{2}\mathrm{d}l_{3} = \mathrm{JdL}_{1}\mathrm{dL}_{2}\mathrm{dL}_{3}$  or  $\mathrm{d}\nu = \mathrm{JdV}$  where  $\mathrm{J} = \operatorname{det}(\mathbf{F})$ .

Given this property, for any function  $G(\mathbf{X})$  or  $g(\mathbf{x}, t)$ , it is very common to use the push forward/pull back when changing variables for integrals defined over subsets of either  $\Omega^0$  or  $\Omega^t$ . That is

$$
\int_ {\mathrm {B} ^ {\mathrm {t}}} \mathrm {g} (\boldsymbol {x}) \mathrm {d} \boldsymbol {x} = \int_ {\mathrm {B} ^ {0}} \mathrm {G} (\boldsymbol {X}) \mathrm {J} (\boldsymbol {X}, \mathrm {t}) \mathrm {d} \boldsymbol {X}, \tag {27}
$$

where  $\mathbf{B}^{\mathrm{t}}$  is an arbitrary subset of  $\Omega^{\mathrm{t}}$ ,  $\mathbf{B}^0$  is the pre-image of  $\mathbf{B}^{\mathrm{t}}$  under  $\phi(\cdot, \mathrm{t})$ ,  $\mathbf{G}$  is the pull back of  $\mathbf{g}$  and  $\mathbf{J}(\mathbf{X}, \mathrm{t})$  is the deformation gradient determinant.

Similar analysis can be done for areas. Consider an arbitrary tiny area  $dS$  in  $\Omega^0$ , denote the corresponding area in  $\Omega^{\dagger}$  with  $ds$ . Assuming their normals are  $\mathbf{N}$  and  $\mathbf{n}$  respectively,

$$
d S = (d S) N, \tag {28}
$$

$$
d s = (d s) n. \tag {29}
$$

Consider another tiny vector  $\mathrm{dL}$  (with corresponding deformed version  $\mathrm{d}l$ ) that determines a tiny volume when combined with  $\mathrm{dS}$  (ds), we have

$$
\mathrm {d} V = \mathrm {d} S \cdot \mathrm {d} L, \tag {30}
$$

$$
\mathrm {d} v = \mathrm {d} s \cdot \mathrm {d} l. \tag {31}
$$

Combining this with the previous result  $\mathrm{d}\nu = \mathrm{J}\mathrm{d}V$ , we get

$$
J d S \cdot d L = d s \cdot (F d L), \tag {32}
$$

where we have used  $\mathrm{d}l = \mathrm{Fd}L$ . Equation 32 needs to be true for any  $\mathrm{d}L$ . That results in the relationship

$$
d s = F ^ {- T} J d S, \tag {33}
$$

or

$$
\mathsf {n d s} = \mathsf {F} ^ {- \top} \mathsf {J N} \mathsf {d S}. \tag {34}
$$

We can then use this relation ship to write the surface integrals as

$$
\int_ {\partial \mathrm {B} ^ {\mathrm {t}}} \mathbf {h} (\mathbf {x}, \mathrm {t}) \cdot \mathbf {n} (\mathbf {x}) \mathrm {d} s (\mathbf {x}) = \int_ {\partial \mathrm {B} ^ {0}} \mathbf {H} (\mathbf {X}) \cdot \mathbf {F} ^ {- \mathrm {T}} (\mathbf {X}, \mathrm {t}) \mathbf {N} (\mathbf {X}) \mathrm {J} (\mathbf {X}, \mathrm {t}) \mathrm {d} S (\mathbf {X}) \tag {35}
$$

where  $\mathsf{H}:\Omega^0\to \mathbb{R}^d$  is the pull back of  $\mathsf{h}:\Omega^{\mathrm{t}}\to \mathbb{R}^{\mathrm{d}}$ ,  $\mathbf{n}(\mathbf{x})$  is the unit outward normal of  $\partial \mathsf{B}^{\mathrm{t}}$  at  $\mathbf{x}$  and  $\mathbf{N}(\mathbf{X})$  is the unit outward normal of  $\partial \mathsf{B}^0$  at  $\mathbf{X}$ . These relationships are very useful when deriving the equations of motion.
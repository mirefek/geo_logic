# GeoLogic
Tool for euclidean geometry aware of logic

## Dependencies
+ Python3
+ pycairo
+ pyGtk3

## Data types

GeoLogic can handle five types of objects: Point (P), Line (L), Circle
(C), Angle (A) (which include a direction of a line or a "length" of
an arc), and Ratio (D) (ratio of products of lengths, including a
length itself). From these five data types, only three of them can be
matipulated using the GUI -- points, lines and circles. Every object
in the GL file is of one of these types, the types of input and output
objects are in the header of every tool.

## Semi-formal logic

The background logical system requires proofs of exact statements
(e.q. line contain a point, two angles are identical, ...) but it only
checks for topological facts numerically
(two circles intersect each other, two triangles are identically oriented).

It is possible to write lemmata for GeoLogic -- some are in the file
macros.gl. However, whenever a lemma is used, GeoLogic also checks whether
the proof of the lemma works in this particular numerical setting.

It is not possible to create lemmata in the user interface yet
(it is a planned feature).

## Automation

As an interactive theorem prover, GeoLogic intentionally does not possess
much automation, especially that would use visual steps. There are basically
four ways in which GeoLogic makes automatic decisions:

+ Gaussian elimination for angles: GeoLogic uses "oriented angle chasing"
  for deriving facts about angles (similar to Full Angle Method).
  Every angle is defined as a difference between the directions of corresponding lines.
  Whenever an equality (modulo rational multiple of pi) can be infered,
  GeoLogic recognizes it.
+ Gaussian elimination for log-distances: Whenever an equality of the form of a ratio
  of products of certain lengths can be infered, GeoLogic recognizes it. Not that
  GeoLogic cannot "add" distances, only multiply, as it is the more common operation
  with them.
+ Extensionality: Whenever x0=y0, x1=y1, ..., xn=yn, then f(x0,...,xn) = f(y0,...,yn)
  for any f being a primitive command / defined macro.
+ Equality triggers: Besides extensionality, there are a few extra 

## Controls

All non-movable logical tools which take only graphical objects (Point / Line / Circle)
on input can be reached using the entry-area in the up right corner of the window.
There are also six "smart" graphical tools that automaticaly run the appropriate logical tool,
and can be used for constructing movable objects.
Right click resets the current tool.

### Ambiguous objects

If two numerically identical objects are about to be shown, geo_logic
shows only one of them. They can be swapped using shift-click. During holding shift,
the ambigous object turn silghtly red.

### Point

+ Free point: click into space
+ Point on line / circle: click on it
+ Intersection: click near intersection
+ More detailed intersection of clines 'a', 'b': drag from 'a' to 'b'
+ Midpoint: click on two points
+ Circle center: drag from circle to its center
+ Foot: click on point, then line / circle near foot
+ Foot: click to point, then drag from one point to another
+ Opposite point on circle: click on point X,
  then on circle containing X near the opposite point
+ Midpoint on an arc: select point X, circle containing X,
  the arc direction, and the second point

### (Parallel) Line

+ Line through two points: click the points (can be free if the second click is into space)
+ Parallel: click on a line (of drag between points), and then click on a point (or into space)
+ Tangent: click on point, and then on circle near possible touchpoint.
+ Angle bisector A B C: select B, drag A->C

### Perpendicular Line

+ Perpendibular bisector: click two points
+ Perpendicular line: click on a line (of drag between points), and then click on a point (or into space)
+ External Angle bisector A B C: select B, drag A->C

### Circle

+ Circle with center O: select O, then click to space / to a point / to a line near possible touchpoint
+ Compass: select circle / drag between points, then select another point / click into space

### Circumcircle

+ Free circle through 1 / 2 points: click the point(s), then into space
+ Circle with diameter: select the diameter, and confirm by clicking on one of the two points
+ Circumcircle: select three points

### Reason

+ Given point X lies on a circle w, infer its distance from center: Select X w
+ Given point X has the right distance from the center of w, infer that w contains X: Select w X
+ Given X Y see the segment A B at the same angle, infer they are concyclic: Select X Y, drag A->B
+ Given X Y A B are concyclic, infer angle equality AXB = AYB: Drag A->B, select X Y
+ Inscribed angle theorem about AXB: Select X, drag A->B
+ Inverse inscribed angle theorem about AXB on a circle w, infer w contains X: Drag A->B, then select X and w
+ Given X lies on a perpendicular bisector l of AB, infer AX=BX: Drag A->B, select l, then X
+ Given AX=BX, infer X lies on a perpendicular bisector l of AB: Drag A->B, select X, then l
+ Given two arcs AB, CD of the same circle w are equal, infer equal distances:
  select w, drag A->B, drag C->D (in the same direction)
+ Given AB=CD on a circle w, infer equal arcs:
  select w, then select consecutively A, B, and C, D (in the same direction)

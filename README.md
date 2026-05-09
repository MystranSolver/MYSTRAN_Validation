# MYSTRAN_Validation
Automated test suite for validation of Mystran.
> [!WARNING]
> It works but the design isn't stable yet and anything might change.

## Run tests
```
py test.py path/to/mystran.exe
```

## Build
Build f06magic somehow or use the included .exe file on Windows.

## Features
Each test case is described by one line in the `cases.txt` file. There are two types - individual values and bulk comparison:
### Individual values

Compares values from the f06 file to a reference value defined on the same line.
This type of test is useful for comparing specific values in the solution to
hand calcululations or published benchmark solutions.

Example line in cases.txt:
```
pth;    my test.dat;   SC/1/DISPLACEMENTS/GID/8/RX;    ;      1.234e-5;     2e-5%
```
This solves the file `my test.dat` then compares rotation about X at grid point
8 to 1.234e-5 with a tolerance that's reasonable for single precision or the 7
digits typical of values in an f06 file.

#### Paths
Values are identified by hierarchical paths, which can lead to one or multiple values. Examples:
- `SC/1/DISPLACEMENTS/GID/8/TY` One value
- `SC/1/SPCFORCES/GID/10-90/TX` A range of 81 grid point IDs.
- `SC/1/SOLIDSTRESSES/EID/4/CORNER/0/XY,YZ,ZX`   A list of three center stress components.
- `SC/1/SOLIDSTRAINS/EID/1,5/CORNER/1-6/XX` Both a list of 2 element IDs and a set of 6 corner numbers, giving 12 values.

The reference value can be either a number or a path that resolves to a single value.

#### Criterion
If the tolerance ends with a `%`, it means **percentage tolerance**. This
criterion is useful for most cases except where the reference value is
zero. Percentage test passes if:
```
100 * |<test value> / <reference value> - 1| <= <tolerance>
```
If there's no `%` symbol in the tolerance field, it means **difference tolerance**.
This criterion is useful where the reference value is zero Difference test
passes if:
```
|<test value> - <reference value>| <= <tolerance>
```

#### Operations
You can apply an operation before comparing to the reference value:
- None: Simply compare the value to the reference value. If there are multiple
values, compare each one independently.
- `SUM`: Sum multiple values. Useful for validating reaction force balance over
multiple nodes.
- `DIFF`: 1st value minus 2nd value.
- `RATIO`: 1st value divided by 2nd value.
- `NORM`: L2 norm. Useful for finding vector magnitude, ensuring that a lot of
values are all zero, or ignoring the sign in an eigenvector.
- `ANGLEFROMX`: Angle of a translational DOF vector (TX, TY, TZ) from the X axis,
ignoring the sign. The path you specify must not include the trailing `/TX`,
`/TY`, or `/TZ`. If you specify multiple grid points, it sums them before
calculating the angle. Useful for validating the direction of deflection of a
mode shape.
- `ANGLEFROMY`: The same as ANGLEFROMX except from the Y axis.
- `ANGLEFROMZ`: The same as ANGLEFROMX except from the Z axis.

#### Grid point transformations
Displacements and SPC forces can be transformed by matrices supplied in a separate
file. The location and filename stem must be the same as the input deck's but with
the extension `.gptransform`. This is useful for validating values in the basic
coordinate system instead of different grid point coordinate systems used in the
f06 file.

#### Shell angles
Shell stress, strain and engineering forces can be rotated by an angle about
the z axis. Specify the rotation angle for the center and four corners in a
separate file. The location and filename stem must be the same as the input
deck's but with the extension `.shellangles`. This is useful for validating
shell stress in the material or basic coordinate systems instead of the element
coordinate system used in the f06 file.

#### Missing rows
Mystran sometimes omits rows with all zero values from the f06 file. These
are treated as zero instead of errors at specific paths, such as
`/SC/*/SPCFORCES/GID/#/*`.

#### Multiple test cases on the same deck
As an optimization, if a test case uses the same input deck as the previous
test case, it will reuse the previous solution without running Mystran again.

### Bulk comparison

> [!WARNING]
> Not working properly yet.

Compares most values in the solution's f06 file to a reference f06 file. This
type of test is useful for discovering bugs -- when compared to MSC -- or detecting
regressions -- when compared to an older Mystran solution.

Example line in cases.txt:
```
mys;    my_test.bdf;     -b=1   ;    0.0;    0.0
```
This solves my_test.bdf then compares displacements at all grid points to
the reference f06 file `reference_mystran/my_test.f06`.

The reference f06 file is from either an earlier version of Mystran or MSC
Nastran and you store it in either the `/reference_mystran` or `/reference_msc`
directory respectively.

Values to compare can be filtered using arguments like `-b=2 -s=1 -g=1,3,7`

Uses F06magic to emulate F06csv.

The criteria and tolerances are not defined yet so don't use them.



## Directory structure

* 📄 `test.py` - The main program
* 📄 `cases.txt` - Definitions of the test cases. Read by test.py.
* 📄 `output.txt` - Detailed output to help you debug test fails. Generated by test.py.
* 📁 `decks` - Input decks for the test cases. They can be organized into subdirectories.
* 📁 `fails` - .f06 files of failed tests to help you debug them. Generated by test.py.
* 📁 `reference_msc` - Reference .f06 solutions generated by MSC Nastran. Same filename stems and directory structure as the input decks.
* 📁 `reference_mystran` - Reference .f06 solutions generated by an earlier version Mystran. Same filename stems and directory structure as the input decks.
* 📁 `working` - Temporary working directory. Contains Mystran's output files, f06magic's script, etc.. Generated by test.py.
# MYSTRAN_Validation
Automated test suite for validation of Mystran.
> [!WARNING]
> It works but the design isn't stable yet and anything might change.

## Run tests
```
py test.py path/to/mystran.exe
```

## Build
Build f06magic somehow or use the included .exe file on Windows. If
you're not using Windows, give the binary the .exe extension.

## Define tests
Each test case is described by one line in the `cases.txt` file. There are two types - individual values and bulk comparison.

Blank lines and white-space-only lines are ignored.

Lines beginning with `#` are comments and are ignored.

`INCLUDE <filename>` on a line includes the contents of the file <filename> at that
point. Useful for organizing test cases or to temporarily disable groups of test
cases you're not using.

White space between fields is ignored.

### Individual values

Compares values from the f06 file to a reference value defined on the same line.
This type of test is useful for comparing specific values in the solution to
hand calcululations or published benchmark solutions.

Example line in cases.txt:
```
pth;    my test.dat;   SC/1/DISPLACEMENTS/GID/8/RX;            ;  1.234e-5;     2e-5%;      blah
        -----------    ---------------------------  ---------     --------      -----       ----
Field 1   Field 2                Field 3             Field 4      Field 5      Field 6    Field 7
       deck filename            test value          operation    reference    tolerance   comment
                                                                   value
```
This solves the file `my test.dat` then compares rotation about X at grid point
8 to 1.234e-5 with a tolerance that's reasonable for single precision or the 7
digits typical of values in an f06 file.

#### Field 2. Deck filename
If it's the same as the previous line, it will reuse the .f06 file without running Mystran again.

#### Field 3. Test value
The test value is a math expression which can include heirarchical paths in the f06 file as variables.
The paths can resolve to one or multiple values. Examples:
- `SC/1/DISPLACEMENTS/GID/8/TY` One value
- `10 * SC/1/DISPLACEMENTS/GID/8/TY` Multiplication
- `SC/1/SPCFORCES/GID/10-90/TX` A range of 81 grid point IDs.
- `SC/1/SOLIDSTRESSES/EID/4/CORNER/0/XY,YZ,ZX`   A list of three center stress components.
- `SC/1/SOLIDSTRAINS/EID/1,5/CORNER/1-6/XX` Both a list of 2 element IDs and a set of 6 corner numbers, giving 12 values.

#### Supported data:
- `DISPLACEMENTS`: TX, TY, TZ, RX, RY, RZ
- `SPCFORCES`: TX, TY, TZ, RX, RY, RZ
- `SOLIDSTRESSES`: GID, XX, YY, ZZ, XY, YZ, ZX, VONMISES
- `SOLIDSTRAINS`: GID, XX, YY, ZZ, XY, YZ, ZX, VONMISES
- `SHELLFORCES`: GID, NXX, NYY, NXY, MXX, MYY, MXY, QX, QY for each CORNER
- `SHELLSTRESSES`: XX, YY, XY, VONMISES for each CORNER and Z1/Z2. GID, ZX, YZ for each CORNER
- `SHELLSTRAINS`: XX, YY, XY for each CORNER and Z1/Z2. GID, ZX, YZ for each CORNER
- `COMPOSITESTRESSES`: 11, 22, 12, 13, 23 for each PLY
- `BUSHFORCES`: FXE, FYE, FZE, MXE, MYE, MZE
- `BUSHSTRESSES`: 1, 2, 3, 4, 5, 6
- `BUSHSTRAINS`: 1, 2, 3, 4, 5, 6
- `EIGENVECTOR`: TX, TY, TZ, RX, RY, RZ
- `REALEIGENVALUES`: EIGENVALUE, CYCLES

#### Midsurface stress and strain
Use `ZMID` instead of `Z1` or `Z2` to calculate the average of the values at
Z1 and Z2. This is useful for validating membrane strain when there's also
bending. This average only equals the midsurface value if Z1 and Z2 were
specified symmetrically in the PSHELL entry.

#### Node averaging
Averaging of solid or shell element corner values to grid points is applied if you
identify a shell stress, strain or force by GID like
`SC/1/SHELLSTRESSES/GID/123/Z1/XX`. The mapping from gid to (eid, corner) is obtained
from all shell stress, strain, and force results in the file. Caution - This mapping
may not be complete because all-zero rows may be omitted from all of them and
therefore won't be included in the average.

#### Moment due to SPC forces
`SC/*/SPCFORCES/GID/*/MXORIGIN`, `SC/*/SPCFORCES/GID/*/MYORIGIN`, and
`SC/*/SPCFORCES/GID/*/MZORIGIN` calculate the components of the moment
about the basic coordinate system origin due to all 6 components of the
SPC force and moment on the grid point. Useful for validating reaction
moment balance. This calculation requires the coordinates of the grid
point so they are read from the input deck and must be defined in the basic
coordinate system.

#### Field 4. Operation
You can apply an operation before comparing to the reference value:
- None: Simply compare the value to the reference value. If there are multiple
values, compare each one independently.
- `SUM`: Sum multiple values. Useful for validating reaction force balance over
multiple nodes.
- `NORM`: L2 norm. Useful for finding vector magnitude, ensuring that a lot of
values are all zero, or ignoring the sign in an eigenvector.
- `ANGLEFROMX`: Angle of a translational DOF vector (TX, TY, TZ) from the X axis,
ignoring the sign. The path you specify must not include the trailing `/TX`,
`/TY`, or `/TZ`. If you specify multiple grid points, it sums them before
calculating the angle. Useful for validating the direction of deflection of a
mode shape.
- `ANGLEFROMY`: The same as ANGLEFROMX except from the Y axis.
- `ANGLEFROMZ`: The same as ANGLEFROMX except from the Z axis.
- `ABSENT`: Pass if the path doesn't exist. Useful for making sure a model that 
should fail didn't produce a solution.

#### Field 5. Reference value

The reference value has the same format as test value but it must resolve to a single
value.

#### Field 6. Tolerance
If the tolerance ends with a `%`, it means **percentage tolerance**. This
criterion is useful for most cases except where the reference value is
zero. Percentage test passes if:
```
100 * |<test value> / <reference value> - 1| <= <tolerance>
```
If there's no `%` symbol in the tolerance field, it means **difference tolerance**.
This criterion is useful where the reference value is zero. Difference test
passes if:
```
|<test value> - <reference value>| <= <tolerance>
```

#### Field 7. Comment and Known failures
If the comment at the end of the line begins with `KNOWNFAIL` then the test case's
result is inverted. ie. KNOWNFAILs must fail. This is useful for unfixed bugs so
they don't pollute the results with fail notices.

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

#### Field 1. Test type
- `mys` means use reference f06 file in `reference_mystran` directory.
- `msc` means use reference f06 file in `reference_msc` directory.

#### Field 2. Deck filename
If it's the same as the previous line, it will reuse the .f06 file without running Mystran again.

#### Field 3. Filter string
Values to compare can be filtered using arguments like `-b=2 -s=1 -g=1,3,7`

F06csv flags like -H are not allowed.

Uses F06magic to emulate F06csv.

#### Fields 4 and 5
The criteria and tolerances are not defined yet so don't use them.

#### Field 6. Comment and Known failures
If the comment at the end of the line begins with `KNOWNFAIL` then the test case's
result is inverted. ie. KNOWNFAILs must fail. This is useful for unfixed bugs so
they don't pollute the results with fail notices.






## Directory structure

* 📄 `test.py` - The main program
* 📄 `cases.txt` - Definitions of the test cases. Read by test.py.
* 📄 `output.txt` - Detailed output to help you debug test fails. Generated by test.py.
* 📁 `decks` - Input decks for the test cases. They can be organized into subdirectories.
* 📁 `fails` - .f06 files of failed tests to help you debug them. Generated by test.py.
* 📁 `reference_msc` - Reference .f06 solutions generated by MSC Nastran. Same filename stems and directory structure as the input decks.
* 📁 `reference_mystran` - Reference .f06 solutions generated by an earlier version Mystran. Same filename stems and directory structure as the input decks.
* 📁 `working` - Temporary working directory. Contains Mystran's output files, f06magic's script, etc.. Generated by test.py.
# imcpython
Python bindings for IMC

## Install instructions
The install will be simplified in the future, but for now these are the necessary steps.


### Clone this project using
```bash
git clone --recursive git://github.com/oysstu/pyimc.git
```
This includes the pybind11 submodule.

### Build DUNE with position independent code
```bash
mkdir dune/build
cd dune/build
cmake -DCMAKE_CXX_FLAGS=-fPIC -flto ..

# Create IMC bindings
# Skip imc_download if using custom IMC bindings
make imc_download
make imc

make
```

### Generate pybind bindings
Export the following environmental variables, where ... are the paths to the dune source folder and dune build folder respectively.
```bash
export DUNE_ROOT= ...
export DUNE_BUILD= ...
```

When in the pyimc root directory run the following command to generate pybind wrapper under src/generated. If using the official IMC specification as described above, the XML path is ${DUNE_BUILD}/IMC/IMC.xml.

```bash
python generate_bindings.py --dune_path=${DUNE_ROOT} --imc_path=${DUNE_BUILD}/IMC/IMC.xml
```

Optionally, a message whitelist can be passed with --whitelist.
Only the messages in this file is then generated, producing a smaller library and shorter build times. 
If an unknown message is parsed, it will simply be returned as the Message baseclass rather than a specialized message.

### Build using setuptools (wrapper around cmake)

```bash
python setup.py build
python setup.py install
```

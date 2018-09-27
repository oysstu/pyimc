# pyimc
Python bindings for [Inter-Module Communication Protocol (IMC)](https://lsts.fe.up.pt/toolchain/imc) used to communicate between modules in the [LSTS toolchain](https://lsts.fe.up.pt/).

### Installation

#### Clone this project using
```bash
git clone --recursive git://github.com/oysstu/pyimc.git
```
This includes the pybind11 submodule.


###### (Optional) Use a specific IMC/Dune version
The setup checks for a folder named imc and dune in the top folder. If these are not found,
they are retrieved from the LSTS repositories (master). To use a different version,
simply add a folder called dune or imc, respectively, in the top folder. They will automatically be used.


#### Build and install using setuptools (wrapper around cmake)

```bash
python3 setup.py install
```

If you use the system python and only want to install for a single user, you can add --user to the install command without needing administrator rights.



###### (Optional) Only generate bindings for a subset of IMC messages
A config file named whitelist.cfg can be placed in the root folder to
only create bindings for a subset of the IMC messages. This can be necessary when compiling on
embedded systems, as the linker comsumes much memory for the full message set.
If an unknown message is parsed, it will be returned as the Message baseclass rather than a specialized message.
Look at minimal_whitelist.cfg for a set of messages that should always be included.


#### Recommendations
- The pyimc library generates stub files for the bindings, meaning that you can have autocomplete and static type checking if your IDE supports them. This can for example be [PyCharm](https://www.jetbrains.com/pycharm/) or [Jedi](https://github.com/davidhalter/jedi)-based editors.


#### TODO

##### Features
- Implement convenience functions for controlling an agent
- Improve networking. Currently the first one is used if a node announces several udp+imc protocols

##### Bugs/issues

##### Testing
- Loss of network interface
- Loss of connectivity

import os, re, sys, platform, subprocess, shutil, urllib.request, zipfile, io, hashlib

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
from distutils.version import LooseVersion

from utils.generate_bindings import IMCPybind, IMCPyi


class CMakeExtension(Extension):
    def __init__(self, name, sourcedir='', subdir=''):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)
        self.subdir = subdir


class CMakeBuild(build_ext):
    def run(self):
        try:
            out = subprocess.check_output(['cmake', '--version'])
        except OSError:
            raise RuntimeError("CMake must be installed to build the following extensions: " +
                               ", ".join(e.name for e in self.extensions))

        if platform.system() == "Windows":
            cmake_version = LooseVersion(re.search(r'version\s*([\d.]+)', out.decode()).group(1))
            if cmake_version < '3.1.0':
                raise RuntimeError("CMake >= 3.1.0 is required on Windows")

        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        cmake_args = ['-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=' + extdir,
                      '-DPYTHON_EXECUTABLE=' + sys.executable,
                      '-DDUNE_PROGRAM_PYTHON=' + sys.executable]

        cfg = 'Debug' if self.debug else 'Release'
        build_args = ['--config', cfg]

        if platform.system() == "Windows":
            cmake_args += ['-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), extdir)]
            if sys.maxsize > 2**32:
                cmake_args += ['-A', 'x64']
            build_args += ['--', '/m']
        else:
            cmake_args += ['-DCMAKE_BUILD_TYPE=' + cfg]
            build_args += ['--', '-j{}'.format(os.cpu_count() if os.cpu_count() is not None else 2)]

        env = os.environ.copy()
        env['CXXFLAGS'] = '{} -DVERSION_INFO=\\"{}\\"'.format(env.get('CXXFLAGS', ''),
                                                              self.distribution.get_version())
        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)


        # Check for dune
        if not os.path.isdir('dune'):
            # Download from LSTS master
            print('Dune not found. Downloading from LSTS git master.')
            dune_master_req = urllib.request.urlopen('https://github.com/LSTS/dune/archive/master.zip')
            dune_master = dune_master_req.read()
            with zipfile.ZipFile(io.BytesIO(dune_master), 'r') as z:
                z.extractall()
                shutil.move('dune-master', 'dune')

        # Check for IMC definition
        if not (os.path.isfile('imc/IMC.xml') or os.path.isfile('IMC/IMC.xml')):
            print('IMC specification not found. Downloading from LSTS git master.')

            # Download from LSTS master
            imc_master_req = urllib.request.urlopen('https://github.com/LSTS/imc/archive/master.zip')
            imc_master = imc_master_req.read()
            with zipfile.ZipFile(io.BytesIO(imc_master), 'r') as z:
                z.extractall()
                shutil.move('imc-master', 'imc')

        # Copy IMC to cmake build folder (to generate dune definitions)
        imc_dir = 'imc' if os.path.isfile('imc/IMC.xml') else 'IMC'
        imc_build = os.path.join(self.build_temp, imc_dir)
        if os.path.isdir(imc_build):
            shutil.rmtree(imc_build)
        shutil.copytree(imc_dir, imc_build)

        # Generate pyimc bindings
        whitelist = []
        if os.path.isfile('whitelist.cfg'):
            with open('whitelist.cfg', 'rt') as f:
                # Ignore empty lines and lines that starts with hashtag
                whitelist = [x.strip().lower() for x in f.readlines() if x.strip() and not x.startswith('#')]
                print('Generating IMC bindings using whitelist.cfg.')

        # Generate md5 of IMC spec
        imc_xml = os.path.join(imc_dir, 'IMC.xml')
        with open(imc_xml, 'rb') as f:
            b_imc_xml = f.read()
        md5 = hashlib.md5()
        md5.update(b_imc_xml)
        imc_md5 = md5.hexdigest()

        # Check for previous md5 and compare
        already_generated = False
        md5_path = os.path.join('src', 'generated', 'imc.md5')
        if os.path.exists(md5_path):
            with open(md5_path, 'rt') as f:
                imc_md5_current = f.read()

            if imc_md5_current == imc_md5:
                already_generated = True
            else:
                # Remove old bindings on MD5 mismatch
                shutil.rmtree(os.path.join('src', 'generated'))

        # Generate bindings if necessary
        if not already_generated:
            print('Generating python bindings.')
            pb = IMCPybind(imc_xml, whitelist=whitelist)
            pb.write_bindings()

        print('Generating stub file for typing hints.')
        pyi = IMCPyi(os.path.join(imc_dir, 'IMC.xml'), whitelist=whitelist)
        pyi.write_pyi()

        print('Compiling with cmake.')
        subprocess.check_call(['cmake', ext.sourcedir] + cmake_args, cwd=self.build_temp, env=env)
        subprocess.check_call(['cmake', '--build', '.'] + build_args, cwd=self.build_temp)

        # Copy pyi file to out dir
        shutil.move('_pyimc.pyi', os.path.join(extdir, '_pyimc.pyi'))

        # Build was successful, write imc md5
        with open(md5_path, 'wt') as f:
            f.write(imc_md5)



if __name__ == '__main__':
    setup(
        name='pyimc',
        version='0.4.dev0',
        author='Oystein Sture',
        author_email='oysstu@gmail.com',
        description='Python bindings for DUNE-IMC',
        license='MIT',
        long_description='',
        packages=['pyimc', 
                  'pyimc.actors', 
                  'pyimc.algorithms', 
                  'pyimc.coordinates', 
                  'pyimc.network'],
        python_requires='>=3.6',
        install_requires=['netifaces'],
        extras_require={'LSFExporter': ['pandas']},
        package_data={'': ['_pyimc.pyi'],
                      'pyimc.coordinates': ['*.pyi'],
                      'pyimc.algorithms': ['*.pyi']},
        include_package_data=True,
        ext_modules=[CMakeExtension('_pyimc')],
        cmdclass=dict(build_ext=CMakeBuild),
        zip_safe=False
    )

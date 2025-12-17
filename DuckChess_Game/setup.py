from setuptools import setup, Extension
import pybind11

ext_modules = [
    Extension(
        "duck_engine",
        ["engine.cpp"],
        include_dirs=[pybind11.get_include()],
        language='c++'
    ),
]

setup(
    name="duck_engine",
    version="1.0",
    ext_modules=ext_modules,
)
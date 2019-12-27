import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
     name='tvm_valuetypes',  
     version='0.0.3',
     author="Emelyanenko Kirill",
     author_email="emelyanenko.kirill@gmail.com",
     description="Collection of utils for handling Telegram Open Network Virtual Machine value types",
     long_description=long_description,
   long_description_content_type="text/markdown",
     url="https://github.com/EmelyanenkoK/tvm_valuetypes",
     packages=setuptools.find_packages(),
     classifiers=[
         "Development Status :: 3 - Alpha",
         "Intended Audience :: Developers",
         "Programming Language :: Python :: 3",
         "License :: Other/Proprietary License",
         "Operating System :: OS Independent",
         "Topic :: Software Development :: Libraries"
     ],
      install_requires=[
          'crc32c', 'bitarray'
      ],
 )

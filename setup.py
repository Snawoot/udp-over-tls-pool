from os import path

from setuptools import setup

this_directory = path.abspath(path.dirname(__file__))  # pylint: disable=invalid-name
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()  # pylint: disable=invalid-name

setup(name='udp_over_tls_pool',
      version='0.1.1',
      description='Network wrapper which transports UDP packets over multiple '
                  'TLS sessions',
      url='https://github.com/Snawoot/udp-over-tls-pool',
      author='Vladislav Yarmak',
      author_email='vladislav-ex-src@vm-0.com',
      license='MIT',
      packages=['udp_over_tls_pool'],
      python_requires='>=3.5.3',
      setup_requires=[
          'wheel',
      ],
      entry_points={
          'console_scripts': [
              'uotp-server=udp_over_tls_pool.server:main',
              'uotp-client=udp_over_tls_pool.client:main',
          ],
      },
      classifiers=[
          "Programming Language :: Python :: 3.5",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
          "Development Status :: 3 - Alpha",
          "Environment :: No Input/Output (Daemon)",
          "Intended Audience :: End Users/Desktop",
          "Intended Audience :: Information Technology",
          "Intended Audience :: Telecommunications Industry",
          "Intended Audience :: System Administrators",
          "Natural Language :: English",
          "Topic :: Internet",
          "Topic :: Security",
      ],
      long_description=long_description,
      long_description_content_type='text/markdown',
      zip_safe=True)

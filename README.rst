This is experimental, to work with jupyter_kernel_mgmt.

You will need docker set up. Build a tagged docker image with the Dockerfile
in this repo, by running::
  
    docker build -t jupyter-kernel-eg .
  
Create a file ``~/.jupyter/docker_kernels.toml`` with contents like this:

.. code-block:: ini

    [kernels.python]
    image = "jupyter-kernel-eg"
    language = "python"
    cwd = "/home/takluyver/scratch"

Then test with ``python3 -m jupyter_docker_kernels``. It should start a kernel
in a docker container, connect to it, get kernel info, and shut it down cleanly.

To use another docker image, ensure that it is built to start the kernel with
a connection file ``/connect/kernel.json`` and a working directory ``/working``.

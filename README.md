# Uv KernelSpecManager for JupyterLab

This is a little bit like [nb_conda_kernels][nbconda], but for uv.

It takes a list of base directories, scan them for uv projects that
have ipykernel as a dependency, and makes them available as kernels in
JupyterLab.

This is a proof of concept.

[nbconda]: https://github.com/anaconda/nb_conda_kernels


See also https://bluss.github.io/pyproject-local-kernel/ which is a production
ready solution using a slightly different method.

## How to Use


1. Install uv-kernels in the same environment as jupyterlab
2. Run Jupyterlab with configuration that enables uv-kernels:

```
jupyter-lab --ServerApp.kernel_spec_manager_class=uv_kernels.UvKernelSpecManager --UvKernelSpecManager.base_directories='["~/src"]'
```

Setting `--ServerApp.kernel_spec_manager_class=uv_kernels.UvKernelSpecManager`
is mandatory. If not on the command-line, set it in the jupyterlab
configuration file. This is similar to how nb_conda_kernels works (it just
changes your jupyterlab configuration for you.)

Note how kernel_spec_manager_class is a global resource. It can't be both
nb_conda_kernels and uv_kernels at the same time! This is how kernel providers
can be a better solution.

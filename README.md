# Uv KernelSpecManager for JupyterLab

This is a little bit like [nb_conda_kernels][nbconda], but for uv.

It takes a list of base directories, scan them for uv projects that
have ipykernel as a dependency, and makes them available as kernels in
JupyterLab.

This is a proof of concept.

[nbconda]: https://github.com/anaconda/nb_conda_kernels


See also https://bluss.github.io/pyproject-local-kernel/ which is a production
ready solution using a slightly different method.

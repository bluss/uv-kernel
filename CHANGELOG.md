
# 0.2.0

- The default configuration is use_uv_run=false,
  which means that it runs the python in the virtualenv directly, not using `uv run`

- For the uv run configuration, use --project, not --directory so that the working directory is correct.

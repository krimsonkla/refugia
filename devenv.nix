{pkgs, ...}: {
  # Node is here for one reason: tests/conformance runs the published page's own
  # scoring kernel against the same vectors the Python engine runs, and that is
  # the only check that can see across the two implementations. CI has node
  # already, so without this the cross-check still runs there -- it would just
  # skip on the machine where the change is being made, which is the worst place
  # to learn about a divergence last.
  packages = [pkgs.nodejs];

  # Dependencies are declared in pyproject.toml and pinned in uv.lock; devenv runs
  # `uv sync` on shell entry so the venv under $DEVENV_STATE/venv always matches.
  # The project installs editable, so `refugia` and `import refugia` resolve
  # without the shell having to put src/ on PYTHONPATH.
  languages.python = {
    enable = true;
    package = pkgs.python312;
    uv = {
      enable = true;
      sync = {
        enable = true;
        allGroups = true;
      };
    };
  };

  # The hooks are the ones the toolchain in pyproject.toml already declares, plus
  # the file-hygiene checks that keep generated data out of the tree. Anything a
  # contributor cannot run from a plain `uv sync` belongs in CI, not here.
  git-hooks.hooks = {
    alejandra.enable = true;
    deadnix.enable = true;

    black.enable = true;
    ruff.enable = true;

    # pylint has to run inside the project venv or it cannot resolve httpx,
    # typer and openpyxl, and reports every import of them as an error. `uv run`
    # is the one spelling that resolves identically with and without nix.
    pylint = {
      enable = true;
      entry = "uv run pylint";
      language = "system";
      types = ["python"];
    };

    # JSONL is one object per line, which is neither valid JSON nor something
    # prettier can reformat without destroying the format.
    check-json = {
      enable = true;
      excludes = ["\\.jsonl$"];
    };
    prettier = {
      enable = true;
      excludes = ["\\.jsonl$"];
    };

    check-added-large-files.enable = true;
    check-merge-conflicts.enable = true;
    check-yaml.enable = true;
    detect-private-keys.enable = true;
    end-of-file-fixer.enable = true;
    trim-trailing-whitespace.enable = true;

    commit-convention = {
      enable = true;
      name = "commit message convention";
      entry = "${pkgs.bash}/bin/bash ${./scripts/commit-msg-convention.sh}";
      language = "system";
      stages = ["commit-msg"];
    };
  };
}

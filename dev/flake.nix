{
  outputs = { ... }: {
    overlays.default = (self: super: {
      python311 = super.python311.override {
        packageOverrides = pyself: pysuper: {
          pytest-mock = pysuper.pytest-mock.overrideAttrs (_: {
            setuptoolsCheckPhase = "true";
            pytestCheckPhase = "true";
            doCheck = false;
          });
          pre-commit = pysuper.pre-commit.overrideAttrs (_: {
            setuptoolsCheckPhase = "true";
            pytestCheckPhase = "true";
            doCheck = false;
          });
          sphinx-better-theme = pysuper.sphinx-better-theme.overrideAttrs
            (_: { pythonCatchConflictsPhase = "true"; });
          sphinx = pysuper.sphinx.overrideAttrs (_: {
            setuptoolsCheckPhase = "true";
            pytestCheckPhase = "true";
            doCheck = false;
          });
        };
      };
    });
  };
}
    

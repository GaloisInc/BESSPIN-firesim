# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = FireSim
SOURCEDIR     = .
BUILDDIR      = _build

FIRESIMDIR    = $(SOURCEDIR)/..

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

clean:
	rm -r _build/html/*
	rm -r _build/doctrees/*

.PHONY: help Makefile install-scala-doc

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)


install-scala-doc:
	git -C $(FIRESIMDIR) submodule update --init sim/midas
	git -C $(FIRESIMDIR) submodule update --init target-design/chipyard
	cd $(FIRESIMDIR)/target-design/chipyard
	git -C $(FIRESIMDIR)/target-design/chipyard submodule update --init --recursive generators
	git -C $(FIRESIMDIR)/target-design/chipyard submodule update --init --recursive tools
	$(MAKE) -C $(FIRESIMDIR)/sim publish-scala-doc FIRESIM_ENV_SOURCED=1 FIRESIM_STANDALONE=1 JAVA_ARGS=



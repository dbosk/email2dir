.PHONY: all
all: email2dir.py

email2dir.py: email2dir.py.nw


.PHONY: all
all: email2dir.pdf

email2dir.pdf: email2dir.tex
email2dir.tex: email2dir.py.nw


.PHONY: test
test: email2dir.py
	pylint3 email2dir.py
	python3 -m flake8 email2dir.py


.PHONY: clean
clean:
	${RM} email2dir.py email2dir.tex email2dir.pdf


INCLUDE_MAKEFILES=./makefiles
include ${INCLUDE_MAKEFILES}/noweb.mk
include ${INCLUDE_MAKEFILES}/tex.mk

#
#  Makefile.java is designed to compile the starter code and create 4700router.
#  Usage:  make -f Makefile.java
#
#  Students must submit a separate Makefile with their submission that compiles 
#  their code. Whether the '4700router' script is created by the Makefile is 
#  the developer's decision. 
#
JFLAGS = -g
JC = javac
JAR = jar

CLASSES = Router.java

default: build

%.class: %.java
	$(JC) $(JFLAGS) $<

build: $(CLASSES:.java=.class)
	@echo "Creating manifest"
	echo "Main-Class: Router" > manifest.txt
	@echo "Creating JAR file"
	$(JAR) cfm router4700.jar manifest.txt *.class
	@echo "Creating executable script 4700router which is used by the simulator"
	echo '#!/bin/bash' > 4700router
	echo 'java -jar router4700.jar "$$@"' >> 4700router
	chmod +x 4700router

clean:
	@echo "Cleaning up..."
	rm -f *.class router4700.jar 4700router manifest.txt

run: build
	./4700router <args>

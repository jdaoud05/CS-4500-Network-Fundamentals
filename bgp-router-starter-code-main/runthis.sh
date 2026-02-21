#!/bin/bash

FILE="/mnt/c/Users/jadda/Documents/NewStuff/Northeastern/Networks/CS-4500-Network-Fundamentals/bgp-router-starter-code-main/Python/4700router.py"
FILE2="/mnt/c/Users/jadda/Documents/NewStuff/Northeastern/Networks/CS-4500-Network-Fundamentals/bgp-router-starter-code-main/4700router"

if [ -x "$FILE2" ]; then
	rm "$FILE2"
fi

cp "$FILE" "4700router"
dos2unix "4700router"
chmod +x "4700router"


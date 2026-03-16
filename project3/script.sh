#!/bin/bash


send="/mnt/c/Users/jadda/Documents/NewStuff/Northeastern/Networks/CS-4500-Network-Fundamentals/project3/4700send"
recv="/mnt/c/Users/jadda/Documents/NewStuff/Northeastern/Networks/CS-4500-Network-Fundamentals/project3/4700recv"

sendpy="/mnt/c/Users/jadda/Documents/NewStuff/Northeastern/Networks/CS-4500-Network-Fundamentals/project3/4700send.py"
recvpy="/mnt/c/Users/jadda/Documents/NewStuff/Northeastern/Networks/CS-4500-Network-Fundamentals/project3/4700recv.py"

if [ -x "$send" ]; then
	rm "$send"
fi

if [ -x "$recv" ]; then
	rm "$recv"
fi

cp "$sendpy" "4700send"
cp "$recvpy" "4700recv"

dos2unix "4700send"
dos2unix "4700recv"

chmod +x "4700recv"
chmod +x "4700send"


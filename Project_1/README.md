# Project 1 CS4700 Network Fundamentals README

##### Project Description 
The client iterates through a list of words and sends each word one by one to the server. As the client receives server feedback, the wordlist narrows down until it obtains the desired word. It understands how to effectively cut down the wordlist based on the marks it receives from each word. It supports TLS encryption  as well, ensuring secure connections.

##### Project Strategy
The strategy I had for this project was simple. After connecting to the server, the client would iteratively go down the wordlist one by one, narrowing it down depending on the marks it received. There were three main cases I implemented:
1. All marks are 0 -- Remove every character marked a 0 from the wordlis
2. One mark is 1 -- Remove every character marked a 0 from the wordlist, while ensuring that there are no duplicate letters
3. One or more marks is 2 -- Keep the character(s) marked as a 2 at the same index in the wordlist. Then, remove all other characters marked a 0, while ensuring that there are no duplicate letters
These 3 cases allowed the client to guess the word in under 500 guesses

##### Improvements
There were several areas of this project where I could have improved, which I will take into account for Project 2. While the client successfully solves the Wordle, the implementation could have been more dynamic by using generalized word-filtering logic instead of hard-coded cases for specific mark patterns. This would allow the client to handle any combination of marks more flexibly and efficiently, potentially reducing runtime. Additionally, as this was my first time coding in Python and my first time programming in a while, there was an initial learning curve, where I had to adapt to the language's syntax and structure. Nontheless, the client consistently finds the correct word, and these reflections highlight areas for improvement in future projects.



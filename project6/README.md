Strategy:
- Started with just sending and parsing a single query
- Then getting the root --> TLD --> authortative chain working
- Bailwick enforcement
- Splitting the authoritative and recursive resolver last

Challenges:
- Getting the root --> TLD --> authoritative chain right
- Understanding Bailiwick enforcement, as coding this was a new concept for both of us

Testing 
- Tested against each of the config files, until all checks passed

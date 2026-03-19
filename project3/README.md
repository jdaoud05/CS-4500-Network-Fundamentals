Challenges:
- the hardest part was tuning the congestion control and timeout parameters for a noisy network. I initially used a timeout floor of 0.5s which was too conservative, which led to a slow recovery. The 10% duplicate rate was also a trap, I considered adding fast retransmit based on duplicate ACKs, but the duplicated packets from the network would have triggered false retransmits and collapsed the congestion window (unnecessarily).
- another challenge was cwnd collapsing too aggressively. my original retransmit loop would reduce the congestion window once per timed-out packet in a single call, so if two packets timed out together the window would 1/2 twice in one round. i fixed this by only updating cwnd once per timeout regardless of how many packets were retransmitted.

Testing:
- i tested using the simulator with the config provided. 
- i ran iterations adjusting timeout floor, initial cwnd, ssthresh, and the cwnd penalty on loss, observing total time and total bytes sent after each change. bytes sent was a useful secondary signal; high bytes relative to data meant too many re-transmissions, pointing to timeout or cwnd issues (rather than throughput limits).
# Documentation of my FTP Client

### Basic overview of client
The client uses two socket connections: a control channel and a data channel

The control channel sends commands and receives responses
The data channel is a separate connection used only to transfer file or directory data


### Issues I faced
I struggled with understanding that FTP uses two different sockets and that they must be used in the correct order. I also had trouble debugging issues where the program would hang without crashing, which made the errors hard to find. Finally, handling both upload and download arguments correctly was challenging and caused several bugs.

### Overview with how I tested my code
I tested my code by running it locally with different commands to upload, download, list, and delete files on the FTP server. I compared my client’s behavior with a standard FTP client to make sure the results matched. I also used the autograder output and error messages to identify and fix bugs.
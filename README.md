# Go-Back-N-ARQ
This is part of CSC/ECE 573 - Internet Protocols Project 2

# How to run the program

First go inside the Go-Back-N implementation directory 
```
cd go_back_n
```

Files `client.py` and `server.py` implement the sender and the receiver logic of Go-Back-N ARQ protocol respectively 

First, run the `server.py` as following. The server always runs in localhost for now. `7735` is the port where the server must run. `output.txt` is the file where the data sent by the client is written to. `0.2` means 20 percent of the packets received will be dropped to simulate network loss. 
```
python3 server.py 7735 output.txt 0.2
```

Next, run the `client.py` as following. The client runs in localhost and binds to an ephemeral port. The server port is mentioned as `7735` here, same as the port where the server is running. `testfile.txt` is the file that the client wishes to send. The first value following the input file denotes the sender window size = 4. MSS follows the sender window size = 500.
```
python3 client.py localhost 7735 testfile.txt 4 500
```

## Task 1 experiment helper

Run the Task 1 sweep locally (varies window size N, fixed MSS=500, loss p=0.05, 5 trials each; generates a 1MB file if missing) and write results to CSV:
```
python experiments/task1_window.py --file go_back_n/testfile.txt --output task1_results.csv
```

# BCIT COMP8005 Assignment 3 - Port Forwarder

#TODO: Find final docs

## Description

Port forwarding is a mechanism that facilitates the forwarding of network traffic (connections) from one machine to another. The most common use of this technique is to allow an access to an externally available service (such as a web server), which is running on a server in a private LAN. In this way, remote client systems are able to connect to servers offering specific services within a private LAN, depending on the port that is used to connect to the service.

## Objective

Design and implement a port forwarding server that will forward incoming connection requests to specific ports/services from any IP address, to any user-specified IP address and port. For example, an inbound connection from 192.168.1.5 to port 80 may be forwarded to 192.168.1.25, port 80, or to 192.168.1.25, port 8005.

## Program Structure 

The port forwarder utilizes a single thread and EPOLL for asynchronous connections. The forwarder creates a listening socket based on the port specified in the config file. The FD for the listening socket is register with EPOLLIN and the main program loop is started. 
The main program loop follows typical EPOLL usage and looking for EPOLLIN and EPOLLOUT events. On a client connection a create_socket_pair() pair method is called. It creates and stores the client socket and then begins the creation of a corresponding socket to the forwarding target. This socket pair relationship is stored in a dictionary for later use. 
These new sockets are then registered with EPOLLIN. On receiving data from either socket (EPOLLIN) the data is read from the source socket and sent to the target socket. If all the data cannot be written to the target socket, the remaining data is then stored in a buffer associated with that socket. The target socket is then registered with EPOLLOUT. Upon receiving the EPOLLOUT signal the rest of the data written to the socket. 
There are socket setup and socket tear down methods that handle the socket create and necessary tracking dictionaries. 


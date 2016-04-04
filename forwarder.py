import select
from socket import *
import sys
import queue
import signal
import csv

DEBUG = True
LISTEN_PORT = 5000
BUFFER_SIZE = 1024
Target = ('localhost', 10001)

# Setup Listening Socket
server_address = ('', LISTEN_PORT)
listen_socket = socket(AF_INET, SOCK_STREAM)
listen_socket.setblocking(0)
listen_socket.bind(server_address)
listen_socket.listen(5)

# Dictionaries to track clients and messages.
message_queues = {}
data_buffer = {}
client_addresses = {}
client_sockets = {}
socket_channels = {}
client_id_counter = []
client_data_counter = []

# create epoll object and register listing socket
epoll = select.epoll()
epoll.register(listen_socket.fileno(), select.EPOLLIN | select.EPOLLET)


def exit_gracefully(signum, frame):
    # restore the original signal handler as otherwise evil things will happen
    # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
    signal.signal(signal.SIGINT, original_sigint)

    try:
        if input("\nReally quit? (y/n)> ").lower().startswith('y'):
            # write_stats(client_id_counter, client_data_counter)

            sys.exit(1)

    except KeyboardInterrupt:
        print("Ok ok, quitting")
        sys.exit(1)

    # restore the exit gracefully handler here
    signal.signal(signal.SIGINT, exit_gracefully)


def print_d(message, debug=True):
    """Prints message if debug is true."""
    if debug:
        print(message, file=sys.stderr)


class Forward_Socket:
    def __init__(self):
        self.forward_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self, host, port):
        try:
            self.forward_socket.connect((host, port))
            return self.forward_socket
        except Exception as e:
            print_d(e)
            return False


def setup_socket(arg1, arg2=None):
    print_d("Entering setup_socket", DEBUG)
    try:
        if arg2 is not None:
            print_d("Creating return socket to " + repr(arg1) + repr(arg2))
            sock = socket(AF_INET, SOCK_STREAM)
            sock.connect((arg1, arg2))
            client_sockets[sock.fileno()] = sock
            message_queues[sock.fileno()] = queue.Queue()
            client_addresses[sock.fileno()] = sock.getpeername()
        else:
            print_d("Setup Socket to {0}: ".format(arg1))
            sock = arg1
            sock.setblocking(0)
            client_sockets[sock.fileno()] = sock
            message_queues[sock.fileno()] = queue.Queue()
        return sock
    except Exception as e:
        print_d("Error in setup_socket: " + repr(e))
        return False


def teardown_socket(sock):
    # print_d("Tearing down socket to: " + sock.getpeername())
    epoll.unregister(sock.fileno())
    sock.close()
    del data_buffer[sock.fileno()]
    del message_queues[sock.fileno()]
    del client_addresses[sock.fileno()]
    del client_sockets[sock.fileno()]


def create_socket_pair():
    # Create and store source socket
    source_socket, source_address = listen_socket.accept()
    source_socket.setblocking(0)
    setup_socket(source_socket)
    client_addresses[source_socket.fileno()] = source_address
    # Create and store target socket
    target_socket = setup_socket(Target[0], Target[1])
    if target_socket:
        # Store socket pair
        socket_channels[source_socket] = target_socket
        socket_channels[target_socket] = source_socket
        # Register source socket for EPOLLIN
        epoll.register(source_socket.fileno(), select.EPOLLIN | select.EPOLLET)
        # Register target socket for EPOLLOUT
        epoll.register(target_socket.fileno(), select.EPOLLET)
        # Register listen socket for EPOLLIN
        epoll.modify(listen_socket.fileno(), select.EPOLLIN | select.EPOLLET)
    else:
        print_d("Can't establish connection with remote server")
        print_d("Closing connection with client side")
        source_socket.close()


def on_recv(source_socket, data):
    # Store message in target socket queue
    target_socket = socket_channels[source_socket]
    message_queues[target_socket.fileno()].put(data)

    # Register source socket for EPOLLOUT
    epoll.modify(source_socket.fileno(), select.EPOLLOUT | select.EPOLLET)


def close_socket_pair(source_socket):
    target_socket = socket_channels[source_socket]
    # Remove source socket from channel
    del socket_channels[source_socket]
    # Remove target socket from channel
    del socket_channels[target_socket]
    # Tear down source_socket
    teardown_socket(source_socket)
    # Tear down target socket.
    teardown_socket(target_socket)

def forward_buffered_data(target_socket):
    offset = target_socket.send(data_buffer[target_socket.fileno()])
    if len (data_buffer[target_socket.fileno()]) > offset:
        data_buffer[target_socket.fileno()] = data_buffer[target_socket.fileno()][offset:]
        epoll.modify(target_socket.fileno(), select.EPOLLOUT)



    # print('in')
    # byteswritten = self.channels[fileno].send(self.buffers[fileno])
    # if len(self.buffers[fileno]) > byteswritten:
    #     self.buffers[fileno] = self.buffers[fileno][byteswritten:]
    #     self.epoll.modify(fileno, select.EPOLLOUT)


def forward_data(source_socket):
    payload = source_socket.recv(BUFFER_SIZE)
    target_socket = socket_channels[source_socket]
    if payload:
        if len(data_buffer[target_socket.fileno()]) > 0:
                data_buffer[target_socket.fileno()] += payload
        else:
            try:
                offset = target_socket.send(payload)
                if len(payload) > offset:
                    data_buffer[target_socket.fileno()] = payload[offset:]
                    epoll.modify(target_socket.fileno(), select.EPOLLOUT | select.EPOLLET)
            except Exception as e:
                close_socket_pair(source_socket)

        # else:
        #         try:
        #             byteswritten = self.channels[fileno].send(data)
        #             print('data sent to target')
        #             if len(data) > byteswritten:
        #                 self.buffers[fileno] = data[byteswritten:]
        #                 self.epoll.modify(fileno, select.EPOLLOUT)
        #         except socket.error:
        #             self.connections[fileno].send(
        #                 bytes("Can't reach server\n", 'UTF-8'))
        #             self.epoll.modify(fileno, 0)
        #             self.connections[fileno].shutdown(socket.SHUT_RDWR)




def run_program():
    # Main Loop
    while True:
        events = epoll.poll(1)
        for fileno, event in events:

            # handle readable client connections
            if event & select.EPOLLIN:
                # handle new connection requests on listen socket
                if fileno == listen_socket.fileno():
                    # Create Socket Pair
                    create_socket_pair()
                else:
                    # TODO replace with forward data method using a simpler message buffer.
                    forward_data(client_sockets[fileno])

                    # try:
                    #     data = client_sockets[fileno].recv(BUFFER_SIZE)
                    #     data_string = data.decode()
                    #     if data:
                    #         on_recv(client_sockets[fileno], data)
                    #     else:  # close connection
                    #         print_d("Closing connection with {0}, no data".format(client_addresses[fileno]))
                    #         close_socket_pair(client_sockets[fileno])
                    # except Exception as e:
                    #     print_d("Closing connection to {0}, ".format(client_addresses[fileno]) + repr(e))
                    #     close_socket_pair(client_sockets[fileno])

            # handle writeable connections
            elif event & select.EPOLLOUT:
                # TODO replace with forward bufferd data method
                forward_buffered_data(client_sockets[fileno])
                # try:
                #     next_msg = message_queues[fileno].get_nowait()
                # except Exception as e:
                #     continue
                #     # print_d("Closing connection to {0}, ".format(client_addresses[fileno]) + repr(e))
                #     # close_socket_pair(client_sockets[fileno])
                # else:
                #     try:
                #         print_d("Sending " + next_msg.decode() + " to {0}".format(client_addresses[fileno]), DEBUG)
                #         client_sockets[fileno].sendall(next_msg)
                #         epoll.modify(fileno, select.EPOLLIN | select.EPOLLET)
                #     except Exception as e:
                #         print_d("Closing connection to {0}, ".format(client_addresses[fileno]) + repr(e))
                #         close_socket_pair(client_sockets[fileno])


                        # handle closed or erroneous connections
            else:
                pass
                # print_d("Closing connection to {0}".format(client_addresses[fileno]))
                # epoll.unregister(fileno)
                # client_sockets[fileno].close()
                # del message_queues[fileno]
                # del client_addresses[fileno]
                # del client_sockets[fileno]  # # Sockets ready to write to


if __name__ == '__main__':
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    run_program()
